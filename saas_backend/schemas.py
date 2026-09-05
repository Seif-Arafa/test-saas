from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------- User ----------


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    org_name: Optional[str] = None


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Plan ----------


class PlanRead(BaseModel):
    id: int
    name: str
    display_name: str
    max_tokens_daily: int
    max_tokens_monthly: int
    max_documents: int
    max_storage_mb: int
    allowed_models: list[str]
    features: dict[str, Any]
    price_cents: int

    model_config = ConfigDict(from_attributes=True)


# ---------- Organization ----------


class OrganizationCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class OrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    settings: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberCreate(BaseModel):
    user_id: int
    role: str = "clinician"


class OrganizationMemberRead(BaseModel):
    id: int
    org_id: int
    user_id: int
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Subscription ----------


class SubscriptionBase(BaseModel):
    status: str = "active"


class SubscriptionCreate(SubscriptionBase):
    user_id: int
    org_id: Optional[int] = None
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None


class SubscriptionRead(SubscriptionBase):
    id: int
    user_id: int
    org_id: Optional[int] = None
    plan_id: Optional[int] = None
    plan_name: Optional[str] = None
    started_at: datetime
    ends_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Document ----------


class DocumentRead(BaseModel):
    id: int
    org_id: int
    title: str
    doc_type: str
    source: str
    status: str
    file_size_bytes: int
    metadata_json: dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- UsageEvent ----------


class UsageEventBase(BaseModel):
    event_type: str
    payload: Optional[str] = None


class UsageEventCreate(UsageEventBase):
    subscription_id: int
    org_id: Optional[int] = None
    resource_type: Optional[str] = None


class UsageEventRead(UsageEventBase):
    id: int
    subscription_id: int
    org_id: Optional[int] = None
    resource_type: Optional[str] = None
    cost_usd: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- AI / RAG ----------


class ChatMessage(BaseModel):
    role: str
    content: str


class Citation(BaseModel):
    document_id: int
    document_title: str
    chunk_id: int
    snippet: str
    page: Optional[int] = None


class ClinicalChatRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: Optional[int] = None
    doc_types: Optional[list[str]] = None
    specialty: Optional[str] = None
    max_tokens: Optional[int] = 500
    model: Optional[str] = None


class ClinicalChatResponse(BaseModel):
    conversation_id: int
    answer: str
    citations: list[Citation]
    disclaimer: str
    model: str
    usage: dict[str, int]


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    max_tokens: Optional[int] = 100
    model: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ConversationRead(BaseModel):
    id: int
    org_id: int
    user_id: int
    title: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageRead(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    citations_json: Optional[list[dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Analytics ----------


class UsageStats(BaseModel):
    total_events: int
    total_tokens: int
    daily_tokens: dict[str, int] = Field(default_factory=dict)
    total_cost_usd: float
    by_event_type: dict[str, int] = Field(default_factory=dict)


class DocumentStats(BaseModel):
    total_documents: int
    by_status: dict[str, int]
    by_doc_type: dict[str, int]
    total_storage_bytes: int


class RagStats(BaseModel):
    total_queries: int
    avg_latency_ms: float
    avg_citations_per_query: float


# ---------- Audit / Jobs ----------


class AuditLogRead(BaseModel):
    id: int
    org_id: int
    user_id: Optional[int] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobRead(BaseModel):
    id: int
    org_id: int
    job_type: str
    status: str
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
