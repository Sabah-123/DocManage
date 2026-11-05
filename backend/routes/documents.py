import os
import uuid
import gc
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from core.database import get_db, User, Document, NamedEntity, UserSubject, AsyncSessionLocal
from auth.auth import get_current_user
from storage.minio_client import minio_client
from agents.ocr_agent import extract_text
from agents.classification_agent import classify_document, classify_document_for_user
from agents.nlp_agent import extract_entities, entities_to_db_objects
from agents.rag_agent import index_document, delete_document_chunks
from models.schemas import DocumentResponse, DocumentList, DocumentRename, UploadResponse
from core.config import settings
from core.rate_limit import limiter

# Import différé pour éviter les imports circulaires (websocket importe config)
def _get_ws_manager():
    from routes.websocket import manager
    return manager

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".txt", ".eml"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo

# File d'attente globale limitée à 1 process pour respecter le budget mémoire 5 Go
heavy_tasks_executor = ThreadPoolExecutor(max_workers=1)

async def _run_heavy_sync_task(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(heavy_tasks_executor, func, *args)

async def process_document_pipeline(
    document_id: int,
    user_id: int,
    file_bytes: bytes,
    file_ext: str,
    user_subjects: list[str] | None = None,
):
    """Pipeline complet de traitement en arrière-plan"""
    db = AsyncSessionLocal()
    try:
        # 1. OCR (Lourd -> Executor unique)
        extracted_text, ocr_engine = await _run_heavy_sync_task(extract_text, file_bytes, file_ext)

        if not extracted_text.strip():
            await _update_status(db, document_id, "error")
            return

        # 2. Classification contextualisée avec les matières de l'utilisateur
        if user_subjects:
            classification = await _run_heavy_sync_task(
                classify_document_for_user, extracted_text, user_subjects
            )
        else:
            classification = await _run_heavy_sync_task(classify_document, extracted_text)

        # 3. Sauvegarde texte extrait dans MinIO
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        processed_path = minio_client.build_object_name(
            user_id, classification.subject, classification.doc_type,
            Path(doc.filename).stem + ".txt"
        )
        minio_client.save_text(
            settings.minio_bucket_processed,
            processed_path,
            extracted_text
        )

        # 4. Mise à jour chemin MinIO raw selon classification
        new_raw_path = minio_client.build_object_name(
            user_id, classification.subject, classification.doc_type, doc.filename
        )

        # 5. Indexation LlamaIndex + ChromaDB (Lourd RAM -> Executor)
        metadata = {
            "filename": doc.original_name,
            "subject": classification.subject,
            "doc_type": classification.doc_type,
            "language": classification.language,
            "minio_processed_path": processed_path,
        }
        num_chunks = await _run_heavy_sync_task(index_document, document_id, user_id, extracted_text, metadata)

        # 6. Entités nommées spaCy (Lourd CPU -> Executor)
        entities = await _run_heavy_sync_task(extract_entities, extracted_text)
        entity_objects = entities_to_db_objects(document_id, entities)
        db.add_all(entity_objects)

        # 7. Mise à jour du document en base
        doc.minio_processed_path = processed_path
        doc.subject = classification.subject
        doc.doc_type = classification.doc_type
        doc.title_suggested = classification.title_suggested
        doc.language = classification.language
        doc.confidence = classification.confidence
        doc.num_chunks = num_chunks
        doc.status = "ready"

        await db.commit()

        # 8. Notification WebSocket : traitement terminé
        try:
            await _get_ws_manager().notify(user_id, {
                "status": "completed",
                "document_id": document_id,
                "message": "Traitement terminé avec succès",
                "subject": classification.subject,
                "doc_type": classification.doc_type,
                "language": classification.language,
                "num_chunks": num_chunks,
            })
        except Exception:
            logger.exception("WS notify (completed) failed for document_id=%s", document_id)

    except Exception as e:
        import logging
        await db.rollback()
        logging.getLogger(__name__).exception(f"[Pipeline error] document_id={document_id}: {e}")
        await _update_status(db, document_id, "error")
        # Notification WebSocket : erreur de traitement
        try:
            await _get_ws_manager().notify(user_id, {
                "status": "error",
                "document_id": document_id,
                "message": "Échec du traitement du document",
            })
        except Exception:
            logger.exception("WS notify (error) failed for document_id=%s", document_id)
    finally:
        await db.close()
        # Forcer le nettoyage de la mémoire vive globale (très important avec PaddleOCR et cv2)
        gc.collect()

async def _update_status(db: AsyncSession, document_id: int, status: str):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = status
        await db.commit()


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("20/hour")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validation extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Lecture et validation taille
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 50 Mo)")

    import magic
    mime = magic.from_buffer(file_bytes[:2048], mime=True)
    ALLOWED_MIMES = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".txt": "text/plain",
        ".eml": "message/rfc822",
    }
    expected = ALLOWED_MIMES.get(ext)
    if not expected or mime != expected:
        raise HTTPException(status_code=400, detail="Contenu du fichier invalide ou potentiellement malveillant.")

    # Nom unique pour MinIO
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    raw_object_name = f"{current_user.id}/raw/{unique_filename}"

    content_type_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".txt": "text/plain", ".eml": "message/rfc822"
    }

    # Upload vers MinIO
    minio_client.upload_file(
        settings.minio_bucket_raw,
        raw_object_name,
        file_bytes,
        content_type_map.get(ext, "application/octet-stream")
    )

    # Création en base avec statut "processing"
    doc = Document(
        user_id=current_user.id,
        filename=unique_filename,
        original_name=file.filename,
        file_type=ext.lstrip("."),
        minio_raw_path=raw_object_name,
        status="processing"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Récupérer les matières de l'utilisateur pour la classification contextualisée
    subjects_result = await db.execute(
        select(UserSubject.name).where(UserSubject.user_id == current_user.id)
    )
    user_subjects = [row[0] for row in subjects_result.all()]

    # Lancement du pipeline en arrière-plan
    background_tasks.add_task(
        process_document_pipeline,
        doc.id, current_user.id, file_bytes, ext, user_subjects
    )

    return UploadResponse(
        document_id=doc.id,
        filename=file.filename,
        status="processing",
        language=None,
        doc_type=None,
        subject=None,
        num_chunks=0,
        message="Document uploadé. Traitement en cours..."
    )


@router.get("/", response_model=DocumentList)
async def list_documents(
    subject: Optional[str] = None,
    doc_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Document).where(Document.user_id == current_user.id)

    if subject:
        query = query.where(Document.subject == subject)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)

    query = query.order_by(Document.created_at.desc())
    result = await db.execute(query)
    docs = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(Document.user_id == current_user.id)
    )
    total = count_result.scalar()

    return DocumentList(documents=list(docs), total=total)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    return doc


@router.get("/{document_id}/download-url")
async def get_download_url(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc or not doc.minio_raw_path:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    url = minio_client.get_presigned_url(
        settings.minio_bucket_raw,
        doc.minio_raw_path,
        expires_hours=1
    )
    return {"url": url, "expires_in": 3600}


@router.patch("/{document_id}/rename", response_model=DocumentResponse)
async def rename_document(
    document_id: int,
    data: DocumentRename,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    doc.original_name = data.new_name
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    # Supprimer de MinIO
    if doc.minio_raw_path:
        minio_client.delete_object(settings.minio_bucket_raw, doc.minio_raw_path)
    if doc.minio_processed_path:
        minio_client.delete_object(settings.minio_bucket_processed, doc.minio_processed_path)

    # Supprimer de ChromaDB
    await _run_heavy_sync_task(delete_document_chunks, document_id, current_user.id)

    # Supprimer de SQLite (cascade sur conversations + entités)
    await db.delete(doc)
    await db.commit()


@router.get("/{document_id}/entities")
async def get_entities(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")

    entities_result = await db.execute(
        select(NamedEntity).where(NamedEntity.document_id == document_id)
    )
    entities = entities_result.scalars().all()
    return {"entities": [{"text": e.entity_text, "label": e.entity_label} for e in entities]}


@router.get("/{document_id}/summary")
async def get_summary(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc or doc.status != "ready":
        raise HTTPException(status_code=404, detail="Document non trouvé ou pas encore traité")

    from agents.rag_agent import summarize_document
    summary = await _run_heavy_sync_task(summarize_document, document_id, current_user.id)
    return {"document_id": document_id, "summary": summary}


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne le texte extrait d'un document stocké dans le bucket MinIO processed.
    Utilisé par le visualiseur frontend pour DOCX et TXT.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document non trouvé")
    if doc.status != "ready":
        raise HTTPException(status_code=425, detail="Document pas encore traité")
    if not doc.minio_processed_path:
        raise HTTPException(status_code=404, detail="Texte extrait non disponible")

    try:
        raw_bytes: bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            minio_client.download_file,
            settings.minio_bucket_processed,
            doc.minio_processed_path,
        )
        return {"content": raw_bytes.decode("utf-8", errors="replace")}
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception(
            "get_document_content: erreur MinIO document_id=%s", document_id
        )
        raise HTTPException(status_code=500, detail="Impossible de lire le texte extrait")

