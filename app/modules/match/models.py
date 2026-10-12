"""Match ORM models: user profile and persisted match results."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class Profile(Base):
    """One row per user: skills, target roles, education, preferences."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    skills: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferences: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utcnow,
        onupdate=utcnow,
    )


class MatchResult(Base):
    """Persisted scoring outcome for a pasted JD or an application."""

    __tablename__ = "match_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job_applications.id", ondelete="SET NULL"), nullable=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str | None] = mapped_column(String(320), nullable=True)
    score: Mapped[int] = mapped_column(Integer)
    breakdown: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow, index=True
    )
