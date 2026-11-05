"""
routes/subjects.py
Gestion des matières/sujets personnalisés par utilisateur.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from auth.auth import get_current_user
from core.database import get_db, User, UserSubject
from core.rate_limit import limiter
from models.schemas import SubjectCreate, SubjectUpdate, SubjectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subjects", tags=["subjects"])

# ─── Données de seed ─────────────────────────────────────────────────────────

_DEFAULT_SUBJECTS: List[dict] = [
    {"name": "Mathématiques", "icon": "🔢", "color": "#4F46E5"},
    {"name": "Physique",       "icon": "⚡", "color": "#0EA5E9"},
    {"name": "Informatique",   "icon": "💻", "color": "#10B981"},
    {"name": "Chimie",         "icon": "🧪", "color": "#F59E0B"},
    {"name": "Histoire",       "icon": "📜", "color": "#8B5CF6"},
    {"name": "Langues",        "icon": "🌍", "color": "#EC4899"},
    {"name": "Économie",       "icon": "📊", "color": "#14B8A6"},
    {"name": "Biologie",       "icon": "🧬", "color": "#22C55E"},
    {"name": "Autre",          "icon": "📁", "color": "#6B7280"},
]


async def seed_default_subjects(user_id: int, db: AsyncSession) -> None:
    """
    Insère les matières par défaut pour un utilisateur.
    Appelable depuis l'inscription ou la route /reset.
    """
    try:
        subjects = [
            UserSubject(
                user_id=user_id,
                name=s["name"],
                icon=s["icon"],
                color=s["color"],
                is_default=True,
            )
            for s in _DEFAULT_SUBJECTS
        ]
        db.add_all(subjects)
        await db.flush()
        logger.info("seed_default_subjects: %d matières créées pour user_id=%s", len(subjects), user_id)
    except Exception:
        logger.exception("seed_default_subjects: échec pour user_id=%s", user_id)
        raise


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[SubjectResponse])
async def list_subjects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retourne toutes les matières de l'utilisateur courant."""
    try:
        result = await db.execute(
            select(UserSubject)
            .where(UserSubject.user_id == current_user.id)
            .order_by(UserSubject.is_default.desc(), UserSubject.name)
        )
        subjects = result.scalars().all()
        return subjects
    except Exception:
        logger.exception("list_subjects: erreur pour user_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la récupération des matières")


@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_subject(
    request: Request,
    data: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crée une nouvelle matière personnalisée pour l'utilisateur."""
    try:
        # Vérification unicité (user_id, name) avant INSERT pour un message clair
        existing = await db.execute(
            select(UserSubject).where(
                UserSubject.user_id == current_user.id,
                UserSubject.name == data.name,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une matière nommée '{data.name}' existe déjà",
            )

        subject = UserSubject(
            user_id=current_user.id,
            name=data.name,
            color=data.color,
            icon=data.icon,
            is_default=False,
        )
        db.add(subject)
        await db.flush()
        await db.refresh(subject)
        logger.info("create_subject: id=%s '%s' pour user_id=%s", subject.id, subject.name, current_user.id)
        return subject
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_subject: erreur pour user_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la création de la matière")


@router.patch("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Modifie le nom, la couleur, l'icône ou le statut par défaut d'une matière."""
    try:
        result = await db.execute(
            select(UserSubject).where(
                UserSubject.id == subject_id,
                UserSubject.user_id == current_user.id,
            )
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise HTTPException(status_code=404, detail="Matière non trouvée")

        # Si renommage, vérifier unicité (user_id, nouveau name)
        if data.name is not None and data.name != subject.name:
            conflict = await db.execute(
                select(UserSubject).where(
                    UserSubject.user_id == current_user.id,
                    UserSubject.name == data.name,
                )
            )
            if conflict.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Une matière nommée '{data.name}' existe déjà",
                )
            subject.name = data.name

        if data.color is not None:
            subject.color = data.color
        if data.icon is not None:
            subject.icon = data.icon
        if data.is_default is not None:
            subject.is_default = data.is_default

        await db.flush()
        await db.refresh(subject)
        logger.info("update_subject: id=%s mis à jour pour user_id=%s", subject_id, current_user.id)
        return subject
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_subject: erreur subject_id=%s user_id=%s", subject_id, current_user.id)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la mise à jour de la matière")


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime une matière.
    Retourne 403 si la matière est marquée is_default=True.
    """
    try:
        result = await db.execute(
            select(UserSubject).where(
                UserSubject.id == subject_id,
                UserSubject.user_id == current_user.id,
            )
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise HTTPException(status_code=404, detail="Matière non trouvée")

        if subject.is_default:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Impossible de supprimer une matière par défaut",
            )

        await db.delete(subject)
        logger.info("delete_subject: id=%s supprimée pour user_id=%s", subject_id, current_user.id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("delete_subject: erreur subject_id=%s user_id=%s", subject_id, current_user.id)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la suppression de la matière")


@router.post("/reset", response_model=List[SubjectResponse], status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_subjects(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Supprime TOUTES les matières de l'utilisateur et réinsère les 9 matières par défaut.
    Rate limit : 5/minute pour éviter les abus.
    """
    try:
        await db.execute(
            delete(UserSubject).where(UserSubject.user_id == current_user.id)
        )
        await db.flush()

        await seed_default_subjects(current_user.id, db)
        await db.flush()

        result = await db.execute(
            select(UserSubject)
            .where(UserSubject.user_id == current_user.id)
            .order_by(UserSubject.name)
        )
        subjects = result.scalars().all()
        logger.info("reset_subjects: %d matières réinitialisées pour user_id=%s", len(subjects), current_user.id)
        return subjects
    except HTTPException:
        raise
    except Exception:
        logger.exception("reset_subjects: erreur pour user_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail="Erreur interne lors de la réinitialisation des matières")
