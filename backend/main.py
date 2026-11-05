import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from core.rate_limit import limiter

from core.database import init_db
from core.config import settings
from auth.auth import router as auth_router
from routes.documents import router as documents_router
from routes.chat import router as chat_router
from routes.dashboard import router as dashboard_router
from routes.subjects import router as subjects_router
from routes.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Créer les répertoires nécessaires
    os.makedirs("./data/chroma", exist_ok=True)
    os.makedirs("./data", exist_ok=True)

    # Initialiser la base SQLite
    await init_db()
    print("Base de données initialisée ")
    if settings.use_groq:
        print(f"LLM : {settings.groq_model} via Groq Cloud")
    elif settings.use_anthropic:
        print(f"LLM : {settings.anthropic_model} via Anthropic (Claude)")
    else:
        print(f"LLM : {settings.ollama_llm_model} via Ollama")
    print(f"Embedding : {settings.embed_model_name}")

    yield
    print("Arrêt du serveur")


app = FastAPI(
    title="Agentic Doc Management API",
    description="Système agentique de compréhension et gestion documentaire",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(subjects_router)
app.include_router(websocket_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_model": settings.groq_model if settings.use_groq else (settings.anthropic_model if settings.use_anthropic else settings.ollama_llm_model),
        "embed_model": settings.embed_model_name,
    }
