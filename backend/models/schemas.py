from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


# ─── Auth ───────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Documents ──────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    language: Optional[str]
    doc_type: Optional[str]
    subject: Optional[str]
    title_suggested: Optional[str]
    confidence: Optional[float]
    num_chunks: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentList(BaseModel):
    documents: List[DocumentResponse]
    total: int


class DocumentRename(BaseModel):
    new_name: str


class ClassificationResult(BaseModel):
    subject: str
    doc_type: str
    title_suggested: str
    language: str
    confidence: float


# ─── Chat / Q&A ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    content: str = Field(max_length=2000)
    document_id: Optional[int] = None
    session_id: Optional[int] = None

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    document_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSource(BaseModel):
    chunk_text: str
    page: Optional[int]
    score: float
    doc_id: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]
    model_used: str
    model_config = ConfigDict(protected_namespaces=())


class ConversationMessage(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationHistory(BaseModel):
    messages: List[ConversationMessage]
    document_id: Optional[int]
    session_id: Optional[int]


# ─── Upload ─────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    document_id: int
    filename: str
    status: str
    language: Optional[str]
    doc_type: Optional[str]
    subject: Optional[str]
    num_chunks: int
    message: str


# ─── Entités nommées ────────────────────────────────────────────────────────

class EntityResponse(BaseModel):
    entity_text: str
    entity_label: str

    model_config = ConfigDict(from_attributes=True)


# ─── Dashboard ──────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_documents: int
    documents_by_subject: dict
    documents_by_type: dict
    recent_activity: List[DocumentResponse]
    total_conversations: int


# ─── User Subjects ───────────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(default=None, max_length=7)
    icon: Optional[str] = Field(default=None, max_length=50)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        import re
        if v is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError("color doit être au format hexadécimal #RRGGBB")
        return v


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    color: Optional[str] = Field(default=None, max_length=7)
    icon: Optional[str] = Field(default=None, max_length=50)
    is_default: Optional[bool] = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        import re
        if v is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError("color doit être au format hexadécimal #RRGGBB")
        return v


class SubjectResponse(BaseModel):
    id: int
    name: str
    color: Optional[str]
    icon: Optional[str]
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
