from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import json

from core.database import get_db, User, Document, Conversation, ChatSession
from auth.auth import get_current_user
from agents.rag_agent import query_documents
from models.schemas import ChatMessage, ChatResponse, ConversationHistory, ChatSessionResponse
from core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])


async def generate_session_title(session_id: int, first_message: str):
    try:
        from core.database import AsyncSessionLocal
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        prompt = f"Génère un titre très court (max 4-5 mots) résumant cette question de l'utilisateur. Ne mets pas de guillemets.\nQuestion: {first_message}"
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15,
            temperature=0.3
        )
        title = response.choices[0].message.content.strip().strip('"').strip("'")
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.title = title
                await db.commit()
    except Exception as e:
        print(f"Error generating title for session {session_id}: {e}")

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    document_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = ChatSession(
        user_id=current_user.id,
        document_id=document_id,
        title="Nouvelle discussion"
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    await db.delete(session)
    await db.commit()

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    message: ChatMessage,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Gestion de la session
    session_id = message.session_id
    if not session_id:
        session = ChatSession(user_id=current_user.id, document_id=message.document_id, title="Nouvelle discussion")
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id
        background_tasks.add_task(generate_session_title, session_id, message.content)
    else:
        # Check if first message in session
        res = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        if not res.first():
            background_tasks.add_task(generate_session_title, session_id, message.content)
            
    # Vérifier que le document appartient à l'utilisateur si spécifié
    doc = None
    if message.document_id is not None:
        result = await db.execute(select(Document).where(Document.id == message.document_id, Document.user_id == current_user.id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document non trouvé")
        if doc.status != "ready":
            raise HTTPException(status_code=400, detail="Document en cours de traitement")

    # Fetch history
    limit = 6
    hist_query = select(Conversation).where(Conversation.user_id == current_user.id, Conversation.session_id == session_id)
    hist_query = hist_query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit)
    hist_result = await db.execute(hist_query)
    hist_msgs = list(reversed(hist_result.scalars().all()))
    history_str = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in hist_msgs])

    intent = "tool" if any(kw in message.content.lower() for kw in 
        ["combien", "list", "supprim", "dernier", "total", "stat", "ajout", "matièr", "matier", "cré", "cree", "module"]) else "rag"

    if intent == "rag" or not settings.use_groq:
        result_data = query_documents(
            question=message.content,
            user_id=current_user.id,
            history=history_str,
            document_id=message.document_id,
            filename=doc.original_name if doc else None,
            file_type=doc.file_type if doc else None,
            top_k=4
        )
        answer = result_data["answer"]
        sources = result_data["sources"]
        model_used = result_data["model_used"]
    else:
        from agents.orchestrator_agent import MCPServer
        mcp_server = MCPServer(db_session=db, user_id=current_user.id)
        mcp_history = [{"role": msg.role, "content": msg.content} for msg in hist_msgs]
        answer = await mcp_server.process_task(task=message.content, history=mcp_history)
        sources = []
        model_used = settings.groq_model

    user_msg = Conversation(user_id=current_user.id, document_id=message.document_id, session_id=session_id, role="user", content=message.content)
    db.add(user_msg)
    
    sources_json = json.dumps([{"chunk": s.chunk_text, "score": s.score} for s in sources], ensure_ascii=False) if sources else None
    assistant_msg = Conversation(user_id=current_user.id, document_id=message.document_id, session_id=session_id, role="assistant", content=answer, sources=sources_json)
    db.add(assistant_msg)
    
    # Update session updated_at
    await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    from sqlalchemy import update
    await db.execute(update(ChatSession).where(ChatSession.id == session_id).values(updated_at=__import__('datetime').datetime.utcnow()))
    
    await db.commit()

    return ChatResponse(answer=answer, sources=sources, model_used=model_used)

@router.get("/history", response_model=ConversationHistory)
async def get_conversation_history(
    session_id: Optional[int] = None,
    document_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Conversation).where(Conversation.user_id == current_user.id)
    if session_id is not None:
        query = query.where(Conversation.session_id == session_id)
    elif document_id is not None:
        query = query.where(Conversation.document_id == document_id)

    query = query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    return ConversationHistory(messages=list(reversed(messages)), document_id=document_id, session_id=session_id)

@router.delete("/history", status_code=204)
async def clear_history(
    session_id: Optional[int] = None,
    document_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = delete(Conversation).where(Conversation.user_id == current_user.id)
    if session_id is not None:
        query = query.where(Conversation.session_id == session_id)
    elif document_id is not None:
        query = query.where(Conversation.document_id == document_id)
    await db.execute(query)
    await db.commit()

@router.get("/stream")
async def stream_answer(
    q: str,
    session_id: Optional[int] = None,
    document_id: Optional[int] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from agents.rag_agent import _get_collection, ensure_initialized
    
    ensure_initialized()
    # We will check if collection is empty later, only for RAG.

    doc_name = None
    if document_id:
        res = await db.execute(select(Document).where(Document.id == document_id))
        doc_obj = res.scalar_one_or_none()
        if doc_obj:
            if doc_obj.status != 'ready':
                async def not_ready_gen():
                    yield f"data: {json.dumps({'token': '⏳ **Veuillez patienter...**', 'done': False})}\n\n"
                    yield f"data: {json.dumps({'token': '', 'done': True, 'session_id': session_id})}\n\n"
                return StreamingResponse(not_ready_gen(), media_type="text/event-stream")
            doc_name = doc_obj.original_name

    if not session_id:
        session = ChatSession(user_id=current_user.id, document_id=document_id, title="Nouvelle discussion")
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id
        asyncio = __import__('asyncio')
        asyncio.create_task(generate_session_title(session_id, q))
    else:
        res = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        if not res.first():
            asyncio = __import__('asyncio')
            asyncio.create_task(generate_session_title(session_id, q))

    hist_query = select(Conversation).where(Conversation.user_id == current_user.id, Conversation.session_id == session_id)
    hist_query = hist_query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(6)
    hist_result = await db.execute(hist_query)
    hist_msgs = list(reversed(hist_result.scalars().all()))

    async def generate():
        from agents.orchestrator_agent import MCPServer
        mcp_server = MCPServer(db_session=db, user_id=current_user.id)
        mcp_history = [{"role": msg.role, "content": msg.content} for msg in hist_msgs]
        
        task_str = q
        if document_id and doc_name:
             task_str = f"[Contexte: l'utilisateur consulte le document {doc_name} (ID: {document_id})] {q}"

        intent = "tool" if any(kw in q.lower() for kw in 
            ["combien", "list", "supprim", "dernier", "total", "stat", "ajout", "matièr", "matier", "cré", "cree", "module"]) else "rag"
        
        real_response = ""
        
        if intent == "rag" or not settings.use_groq:
            collection = _get_collection(current_user.id)
            if collection.count() == 0:
                real_response = "Aucun document indexé. Veuillez d'abord uploader un document pour pouvoir poser des questions sur leur contenu."
                yield f"data: {json.dumps({'token': real_response, 'done': False})}\n\n"
            else:
                from agents.rag_agent import query_documents_stream
                history_str = "\n".join([f"{msg.role.upper()}: {msg.content}" for msg in hist_msgs])
                async for token in query_documents_stream(
                    question=q, user_id=current_user.id, history=history_str,
                    document_id=document_id, filename=doc_name, file_type=None
                ):
                    if token:
                        real_response += token
                        yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
        else:
            async for chunk_dict in mcp_server.process_task_stream(task=task_str, history=mcp_history):
                token = chunk_dict.get("token", "")
                if token:
                    real_response += token
                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                
        yield f"data: {json.dumps({'token': '', 'done': True, 'session_id': session_id})}\n\n"

        from core.database import AsyncSessionLocal
        from sqlalchemy import update
        async with AsyncSessionLocal() as save_db:
            clean_response = real_response.strip()
            if "⏳" in clean_response:
                 clean_response = clean_response.split("...*\n\n")[-1].strip()
            
            user_conv = Conversation(user_id=current_user.id, document_id=document_id, session_id=session_id, role="user", content=q)
            assistant_conv = Conversation(user_id=current_user.id, document_id=document_id, session_id=session_id, role="assistant", content=clean_response if clean_response else real_response)
            save_db.add(user_conv)
            save_db.add(assistant_conv)
            await save_db.execute(update(ChatSession).where(ChatSession.id == session_id).values(updated_at=__import__('datetime').datetime.utcnow()))
            await save_db.commit()

    return StreamingResponse(generate(), media_type="text/event-stream")
