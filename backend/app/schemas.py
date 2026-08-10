from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: Literal["user", "admin"]
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FreeResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    youtube_url: str = Field(min_length=1, max_length=1024)
    level: str = Field(default="beginner", max_length=64)
    category: str = Field(default="general", max_length=128)


class FreeResourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    topic_tags: list[str] | None = None
    youtube_url: str | None = Field(default=None, min_length=1, max_length=1024)
    level: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=128)


class FreeResourceOut(BaseModel):
    id: int
    title: str
    description: str
    topic_tags: list[str]
    youtube_url: str
    level: str
    category: str
    sync_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecommendedResourceOut(FreeResourceOut):
    """Catalog resource plus the Udemy signal that motivated this pick."""

    because: str | None = None


class RecommendationOut(BaseModel):
    id: int
    user_id: int
    narrative: str
    resource_ids: list[int]
    trigger_reason: str
    generated_at: datetime
    expires_at: datetime
    resources: list[RecommendedResourceOut] = Field(default_factory=list)
    match_meta: list[dict] = Field(default_factory=list)
    source_summary: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


EventType = Literal["view", "search", "click", "time_spent"]


class EventIn(BaseModel):
    event_type: EventType
    source: str = Field(default="udemy", max_length=128)
    raw_metadata: dict = Field(default_factory=dict)


class EventBatchRequest(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=500)


class EventOut(BaseModel):
    id: int
    user_id: int
    event_type: str
    source: str
    raw_metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class EventBatchResponse(BaseModel):
    inserted: int
    triggered: bool
    trigger_reason: str | None = None
    recommendation: RecommendationOut | None = None


class LatestRecommendationResponse(BaseModel):
    recommendation: RecommendationOut | None


class AgentStatusOut(BaseModel):
    """Transparent agent progress — no LLM; helps UX show when free path will update."""

    has_recommendation: bool
    new_event_count: int
    threshold: int
    events_until_next: int
    cooldown_seconds: int
    cooldown_remaining_seconds: float
    ready_to_run: bool
    blocked_by_cooldown: bool
    last_generated_at: datetime | None = None
    last_trigger_reason: str | None = None
    expires_at: datetime | None = None
    resource_ids: list[int] = Field(default_factory=list)
    status_label: str
    skip_reason: str | None = None
    family_counts: dict | None = None

