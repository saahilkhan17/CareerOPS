"""Tracker persistence. Every query is scoped to (id, user_id). No machine logic."""

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models import (
    ApplicationStatus,
    Company,
    JobApplication,
    Note,
    Reminder,
    StatusHistory,
)

SORT_FIELDS = {
    "created_at": JobApplication.created_at,
    "applied_at": JobApplication.applied_at,
    "title": JobApplication.title,
}


async def get_or_create_company(session: AsyncSession, name: str) -> Company:
    """Fetch a company by exact name, creating it (race-safe) when missing."""
    cleaned = name.strip()
    result = await session.execute(select(Company).where(Company.name == cleaned))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    company = Company(name=cleaned)
    session.add(company)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(select(Company).where(Company.name == cleaned))
        retry = result.scalar_one()
        return retry
    return company


async def create_application(
    session: AsyncSession,
    user_id: uuid.UUID,
    company: Company,
    **fields: object,
) -> JobApplication:
    row = JobApplication(user_id=user_id, company_id=company.id, **fields)
    session.add(row)
    await session.flush()
    return row


async def get_application(
    session: AsyncSession, user_id: uuid.UUID, app_id: uuid.UUID
) -> JobApplication | None:
    result = await session.execute(
        select(JobApplication).where(JobApplication.id == app_id, JobApplication.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_applications(
    session: AsyncSession,
    user_id: uuid.UUID,
    status: ApplicationStatus | None = None,
    company: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    query: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[JobApplication], int]:
    """Filtered, sorted, paginated applications plus the total count."""
    stmt = (
        select(JobApplication)
        .join(Company, Company.id == JobApplication.company_id)
        .where(JobApplication.user_id == user_id)
    )
    if status is not None:
        stmt = stmt.where(JobApplication.status == status)
    if company:
        stmt = stmt.where(Company.name.ilike(f"%{company}%"))
    if date_from is not None:
        stmt = stmt.where(JobApplication.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(JobApplication.created_at <= date_to)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                JobApplication.title.ilike(like),
                Company.name.ilike(like),
                JobApplication.notes.ilike(like),
            )
        )
    sort_col = SORT_FIELDS.get(sort_by, JobApplication.created_at)
    stmt = stmt.order_by(
        sort_col.desc() if order == "desc" else sort_col.asc(),
        JobApplication.id.asc(),
    )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.execute(stmt.limit(limit).offset(offset))
    return list(rows.scalars().all()), total or 0


async def delete_application(session: AsyncSession, row: JobApplication) -> None:
    await session.delete(row)
    await session.flush()


async def add_history(
    session: AsyncSession,
    application_id: uuid.UUID,
    from_status: ApplicationStatus | None,
    to_status: ApplicationStatus,
) -> StatusHistory:
    row = StatusHistory(application_id=application_id, from_status=from_status, to_status=to_status)
    session.add(row)
    await session.flush()
    return row


async def list_history(session: AsyncSession, application_id: uuid.UUID) -> list[StatusHistory]:
    result = await session.execute(
        select(StatusHistory)
        .where(StatusHistory.application_id == application_id)
        .order_by(StatusHistory.changed_at.asc(), StatusHistory.id.asc())
    )
    return list(result.scalars().all())


async def add_note(session: AsyncSession, application_id: uuid.UUID, body: str) -> Note:
    row = Note(application_id=application_id, body=body)
    session.add(row)
    await session.flush()
    return row


async def list_notes(session: AsyncSession, application_id: uuid.UUID) -> list[Note]:
    result = await session.execute(
        select(Note)
        .where(Note.application_id == application_id)
        .order_by(Note.created_at.asc(), Note.id.asc())
    )
    return list(result.scalars().all())


async def add_reminder(
    session: AsyncSession, application_id: uuid.UUID, due_at: datetime
) -> Reminder:
    row = Reminder(application_id=application_id, due_at=due_at)
    session.add(row)
    await session.flush()
    return row


async def list_reminders(session: AsyncSession, application_id: uuid.UUID) -> list[Reminder]:
    result = await session.execute(
        select(Reminder)
        .where(Reminder.application_id == application_id)
        .order_by(Reminder.due_at.asc(), Reminder.id.asc())
    )
    return list(result.scalars().all())


async def get_reminder(
    session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID
) -> Reminder | None:
    """Fetch a reminder only when it belongs to one of the user's applications."""
    result = await session.execute(
        select(Reminder)
        .join(JobApplication, JobApplication.id == Reminder.application_id)
        .where(Reminder.id == reminder_id, JobApplication.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def due_reminders(
    session: AsyncSession, user_id: uuid.UUID, cutoff: datetime
) -> list[Reminder]:
    """Undone reminders due at or before cutoff, oldest first."""
    result = await session.execute(
        select(Reminder)
        .join(JobApplication, JobApplication.id == Reminder.application_id)
        .where(
            JobApplication.user_id == user_id,
            Reminder.done.is_(False),
            Reminder.due_at <= cutoff,
        )
        .order_by(Reminder.due_at.asc(), Reminder.id.asc())
    )
    return list(result.scalars().all())
