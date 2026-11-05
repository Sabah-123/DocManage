from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db, User, Document, Conversation
from auth.auth import get_current_user
from models.schemas import DashboardStats, DocumentResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Total documents
    total_result = await db.execute(
        select(func.count()).where(Document.user_id == current_user.id)
    )
    total = total_result.scalar() or 0

    # Par matière
    subject_result = await db.execute(
        select(Document.subject, func.count().label("count"))
        .where(Document.user_id == current_user.id)
        .group_by(Document.subject)
    )
    by_subject = {row.subject or "Non classifié": row.count for row in subject_result}

    # Par type
    type_result = await db.execute(
        select(Document.doc_type, func.count().label("count"))
        .where(Document.user_id == current_user.id)
        .group_by(Document.doc_type)
    )
    by_type = {row.doc_type or "Non classifié": row.count for row in type_result}

    # Activité récente (5 derniers docs)
    recent_result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()

    # Total conversations
    conv_result = await db.execute(
        select(func.count()).where(Conversation.user_id == current_user.id)
    )
    total_conv = conv_result.scalar() or 0

    return DashboardStats(
        total_documents=total,
        documents_by_subject=by_subject,
        documents_by_type=by_type,
        recent_activity=list(recent),
        total_conversations=total_conv
    )
