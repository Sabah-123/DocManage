import chromadb
from typing import List, Optional, Dict, Any
from llama_index.core import (
    VectorStoreIndex,
    Document as LlamaDocument,
    Settings as LlamaSettings,
    StorageContext,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
import threading

from core.config import settings
from models.schemas import ChatSource

# ─── Initialisation des modèles (une seule fois) ────────────────────────────

def _init_llama_settings():
    LlamaSettings.embed_model = HuggingFaceEmbedding(
        model_name=settings.embed_model_name,
        query_instruction=settings.embed_query_prefix,
        text_instruction=settings.embed_passage_prefix,
    )
    LlamaSettings.llm = Groq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.1,
    )
    LlamaSettings.node_parser = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50,
        paragraph_separator="\n\n",
    )


_llama_initialized = False
_llama_init_lock = threading.Lock()

def ensure_initialized():
    global _llama_initialized
    if not _llama_initialized:
        with _llama_init_lock:
            if not _llama_initialized:
                _init_llama_settings()
                _llama_initialized = True


# ─── Client ChromaDB ────────────────────────────────────────────────────────

_chroma_client = None
_chroma_lock = threading.Lock()

def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        with _chroma_lock:
            if _chroma_client is None:
                _chroma_client = chromadb.PersistentClient(
                    path=settings.chroma_path,
                    settings=chromadb.config.Settings(anonymized_telemetry=False)
                )
    return _chroma_client


def _get_collection(user_id: int):
    client = _get_chroma_client()
    collection_name = f"{settings.chroma_collection}_user_{user_id}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )


# ─── Indexation ─────────────────────────────────────────────────────────────

def index_document(
    document_id: int,
    user_id: int,
    text: str,
    metadata: Dict[str, Any]
) -> int:
    """
    Indexe un document dans ChromaDB.
    Retourne le nombre de chunks créés.
    """
    ensure_initialized()

    collection = _get_collection(user_id)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # IMPORTANT: ne PAS utiliser 'document_id' comme clé metadata car
    # LlamaIndex l'écrase avec son propre UUID interne (doc_id/ref_doc_id).
    # On utilise 'sql_doc_id' à la place pour stocker notre ID SQLite.
    llama_doc = LlamaDocument(
        text=text,
        metadata={
            "sql_doc_id": str(document_id),
            "user_id": str(user_id),
            "filename": metadata.get("filename", ""),
            "subject": metadata.get("subject", ""),
            "doc_type": metadata.get("doc_type", ""),
            "language": metadata.get("language", "fr"),
            "minio_path": metadata.get("minio_processed_path", ""),
        }
    )

    index = VectorStoreIndex.from_documents(
        [llama_doc],
        storage_context=storage_context,
        show_progress=False,
    )

    # Compter les chunks créés
    results = collection.get(where={"sql_doc_id": str(document_id)})
    count = len(results["ids"]) if results else 0
    return count


def delete_document_chunks(document_id: int, user_id: int):
    """Supprime tous les chunks d'un document de ChromaDB"""
    try:
        collection = _get_collection(user_id)
        results = collection.get(
            where={"sql_doc_id": str(document_id)}
        )
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass


# ─── Recherche et Q&A ───────────────────────────────────────────────────────

QA_PROMPT = """Tu es un assistant expert spécialisé dans l'analyse de documents.

INFORMATIONS SUR LE DOCUMENT :
{doc_context}

CONTENU EXTRAIT (tu dois l'utiliser pour répondre) :
{context}

HISTORIQUE DE LA CONVERSATION :
{history}

QUESTION DE L'UTILISATEUR :
{question}

INSTRUCTIONS :
- Réponds en français de manière précise.
- Si l'utilisateur demande un résumé, utilise les extraits fournis pour synthétiser les points clés.
- MÊME SI LE DOCUMENT EST UNE IMAGE, le texte extrait via OCR t'est fourni ci-dessus. Ne dis JAMAIS que tu ne peux pas lire une image ou que son contenu n'est pas disponible.
- Ne dis JAMAIS que tu n'as pas accès au document, car le contenu pertinent t'est fourni ci-dessus.
- Si le contenu est insuffisant, résume ce que tu as et demande des précisions.
"""




def query_documents(
    question: str,
    user_id: int,
    history: str = "",
    document_id: Optional[int] = None,
    filename: Optional[str] = None,
    file_type: Optional[str] = None,
    top_k: int = 4
) -> Dict[str, Any]:
    """
    Recherche sémantique + génération de réponse.
    Retourne dict avec answer, sources, model_used.
    """
    ensure_initialized()

    # Augmenter top_k si on demande un résumé
    is_summary_request = any(kw in question.lower() for kw in ["résume", "resume", "synthèse", "synthese", "summary"])
    actual_top_k = 10 if is_summary_request else top_k

    collection = _get_collection(user_id)

    if collection.count() == 0:
        return {
            "answer": "Aucun document indexé. Veuillez d'abord uploader des documents.",
            "sources": [],
            "model_used": settings.groq_model
        }

    # Filtre optionnel par document (utilise sql_doc_id, pas document_id)
    where_filter = None
    if document_id is not None:
        where_filter = {"sql_doc_id": str(document_id)}

    # Recherche vectorielle directe pour récupérer les sources
    # NOTE: get_query_embedding() ajoute déjà le query_instruction ("query: ")
    # automatiquement, donc on ne rajoute PAS le préfixe manuellement.
    embed_model = LlamaSettings.embed_model
    query_embedding = embed_model.get_query_embedding(question)

    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": min(actual_top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"]
    }
    if where_filter:
        query_params["where"] = where_filter

    results = collection.query(**query_params)

    chunks = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results["distances"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []

    if not chunks:
        return {
            "answer": "Aucun passage pertinent trouvé pour cette question.",
            "sources": [],
            "model_used": settings.groq_model
        }

    # Construire le contexte
    context_parts = []
    sources = []
    for i, (chunk, distance, meta) in enumerate(zip(chunks, distances, metadatas)):
        context_parts.append(f"[Extrait {i+1}] {chunk}")
        score = max(0.0, 1.0 - distance)
        sources.append(ChatSource(
            chunk_text=chunk[:300] + "..." if len(chunk) > 300 else chunk,
            page=None,
            score=round(score, 3),
            doc_id=int(meta.get("sql_doc_id", 0))
        ))

    context = "\n\n".join(context_parts)
    is_image = file_type in ["jpg", "jpeg", "png", "bmp", "tiff", "webp"]
    doc_context = f"Le document actuel est une IMAGE nommée : {filename}. Les extraits fournis sont issus d'une reconnaissance optique (OCR)." if is_image else f"Le document actuel s'appelle : {filename}"
    
    prompt = QA_PROMPT.format(doc_context=doc_context if filename else "", context=context, history=history, question=question)

    # Générer la réponse avec Qwen
    llm = LlamaSettings.llm
    response = llm.complete(prompt)
    answer = str(response).strip()

    return {
        "answer": answer,
        "sources": sources,
        "model_used": settings.groq_model
    }


async def query_documents_stream(
    question: str,
    user_id: int,
    history: str = "",
    document_id: Optional[int] = None,
    filename: Optional[str] = None,
    file_type: Optional[str] = None,
    top_k: int = 4
):
    """Version streaming de query_documents"""
    ensure_initialized()

    is_summary_request = any(kw in question.lower() for kw in ["résume", "resume", "synthèse", "synthese", "summary"])
    actual_top_k = 10 if is_summary_request else top_k

    collection = _get_collection(user_id)
    if collection.count() == 0:
        yield "Aucun document indexé."
        return

    where_filter = {"sql_doc_id": str(document_id)} if document_id else None
    embed_model = LlamaSettings.embed_model
    query_embedding = embed_model.get_query_embedding(question)

    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": min(actual_top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"]
    }
    if where_filter:
        query_params["where"] = where_filter

    results = collection.query(**query_params)
    chunks = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results["distances"] else []
    
    if not chunks:
        yield "Aucun passage pertinent trouvé."
        return

    context_parts = [f"[Extrait {i+1}] {chunk}" for i, chunk in enumerate(chunks)]
    context = "\n\n".join(context_parts)
    is_image = file_type in ["jpg", "jpeg", "png", "bmp", "tiff", "webp"]
    doc_context = f"Le document actuel est une IMAGE nommée : {filename}. Les extraits fournis sont issus d'une reconnaissance optique (OCR)." if is_image else f"Le document actuel s'appelle : {filename}"
    
    prompt = QA_PROMPT.format(doc_context=doc_context if filename else "", context=context, history=history, question=question)

    llm = LlamaSettings.llm
    response_gen = llm.stream_complete(prompt)
    for response in response_gen:
        yield response.delta


def summarize_document(document_id: int, user_id: int) -> str:
    """Génère un résumé du document via ses chunks indexés"""
    ensure_initialized()

    collection = _get_collection(user_id)

    results = collection.get(
        where={"sql_doc_id": str(document_id)},
        include=["documents"]
    )

    if not results or not results["documents"]:
        return "Document non trouvé dans l'index."

    # Prendre les 6 premiers chunks
    chunks = results["documents"][:6]
    text_sample = "\n\n".join(chunks)[:4000]

    prompt = f"""Génère un résumé concis et structuré du document suivant en français.
Le résumé doit :
- Identifier le type et la matière du document
- Lister les points clés (5 maximum)
- Mentionner les formules ou concepts importants si présents
- Faire entre 150 et 300 mots

Document :
{text_sample}

Résumé :"""

    llm = LlamaSettings.llm
    response = llm.complete(prompt)
    return str(response).strip()
