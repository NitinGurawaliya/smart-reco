from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    events = relationship("Event", back_populates="user")
    recommendations = relationship("Recommendation", back_populates="user")


class FreeResource(Base):
    __tablename__ = "free_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topic_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    youtube_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    level: Mapped[str] = mapped_column(String(64), nullable=False, default="beginner")
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="general")
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="udemy")
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user = relationship("User", back_populates="events")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resource_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{ "resource_id": 5, "because": "FastAPI — The Complete Course" }, ...]
    match_meta: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Snapshot of activity that produced this row (UI tags must use this, not live events)
    source_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="recommendations")
