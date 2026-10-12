"""Tracker ORM models: companies, applications, history, notes, reminders."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base
from app.modules.auth.models import User  # noqa: F401  (register User metadata here)


class ApplicationStatus(enum.StrEnum):
    """Application lifecycle states."""

    SAVED = "saved"
    APPLIED = "applied"
    OA = "oa"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Company(Base):
    """Shared company lookup, deduplicated by name."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)


class JobApplication(Base):
    """One user's application to one role."""

    __tablename__ = "job_applications"
    __table_args__ = (
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(320))
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.SAVED,
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=utcnow,
        onupdate=utcnow,
    )

    company: Mapped[Company] = relationship(lazy="joined")


class StatusHistory(Base):
    """Append-only record of every status change."""

    __tablename__ = "status_history"
    __table_args__ = (Index("ix_history_application", "application_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_applications.id", ondelete="CASCADE")
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), nullable=True
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )


class Note(Base):
    """Timestamped note on an application."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )


class Reminder(Base):
    """Follow-up reminder on an application."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_applications.id", ondelete="CASCADE"), index=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=utcnow
    )
