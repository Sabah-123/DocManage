from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import field_validator, ValidationInfo  # ✅ ICI (en haut)

class Settings(BaseSettings):
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_hours: int = 8

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False
    minio_bucket_raw: str = "docs-raw"
    minio_bucket_processed: str = "docs-processed"
    minio_bucket_images: str = "docs-images"

    # Groq
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # Embedding
    embed_model_name: str = "intfloat/multilingual-e5-base"
    embed_query_prefix: str = "query: "
    embed_passage_prefix: str = "passage: "

    # ChromaDB
    chroma_path: str = "./data/chroma"
    chroma_collection: str = "documents"

    # SQLite
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # OCR
    tesseract_cmd: str = "/usr/bin/tesseract"
    paddle_use_gpu: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="allow"
    )

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY doit faire au moins 32 caractères")
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()