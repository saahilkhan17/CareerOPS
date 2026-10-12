"""Tracker request/response schemas (Pydantic v2, never ORM objects)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracker.models import ApplicationStatus


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    website: str | None


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=320)
    title: str = Field(min_length=1, max_length=320)
    url: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=320)
    notes: str | None = None
    resume_version: str | None = Field(default=None, max_length=120)
    status: ApplicationStatus = ApplicationStatus.SAVED
    applied_at: datetime | None = None


class ApplicationUpdate(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=320)
    title: str | None = Field(default=None, min_length=1, max_length=320)
    url: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=320)
    notes: str | None = None
    resume_version: str | None = Field(default=None, max_length=120)
    applied_at: datetime | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    url: str | None
    source: str | None
    location: str | None
    notes: str | None
    resume_version: str | None
    status: ApplicationStatus
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    company: CompanyOut


class StatusChangeIn(BaseModel):
    to_status: ApplicationStatus


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_at: datetime


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    body: str
    created_at: datetime


class ReminderCreate(BaseModel):
    due_at: datetime


class ReminderDoneIn(BaseModel):
    done: bool = True


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    due_at: datetime
    done: bool
    created_at: datetime


class PaginatedApplications(BaseModel):
    items: list[ApplicationOut]
    total: int
    limit: int
    offset: int
