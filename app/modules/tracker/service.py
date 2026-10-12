"""Tracker business logic: state machine, history, notes, reminders, export."""

import csv
import io
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.audit import repository as audit_repository
from app.modules.auth.models import User
from app.modules.tracker import repository
from app.modules.tracker.models import ApplicationStatus, JobApplication
from app.modules.tracker.schemas import ApplicationCreate, ApplicationUpdate

# Forward-only pipeline; rejected/withdrawn are terminal (see ADR-0007).
ALLOWED: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.SAVED: {ApplicationStatus.APPLIED, ApplicationStatus.WITHDRAWN},
    ApplicationStatus.APPLIED: {
        ApplicationStatus.OA,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OA: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFER: {ApplicationStatus.WITHDRAWN},
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}


class TransitionError(ValueError):
    """Raised when a status change is not in the machine (router maps to 409)."""


class NotFoundError(LookupError):
    """Raised when the row is missing or belongs to another user (router: 404)."""


def validate_transition(
    from_status: ApplicationStatus | None, to_status: ApplicationStatus
) -> None:
    """Pure guard: raise TransitionError unless None→any or an allowed edge."""
    if from_status is None:
        return
    if to_status not in ALLOWED[from_status]:
        raise TransitionError(f"cannot move from {from_status.value} to {to_status.value}")


async def get_owned(session: AsyncSession, user: User, app_id: uuid.UUID) -> JobApplication:
    """Fetch one of the user's applications or raise NotFoundError."""
    row = await repository.get_application(session, user.id, app_id)
    if row is None:
        raise NotFoundError(str(app_id))
    return row


async def create_application(
    session: AsyncSession, user: User, payload: ApplicationCreate
) -> JobApplication:
    """Create an application plus its initial history row in one commit."""
    validate_transition(None, payload.status)
    company = await repository.get_or_create_company(session, payload.company)
    data = payload.model_dump(exclude={"company"})
    row = await repository.create_application(session, user.id, company, **data)
    await repository.add_history(session, row.id, None, row.status)
    await audit_repository.log(
        session, user.id, "tracker.application.create", "application", row.id
    )
    await session.commit()
    await session.refresh(row)
    return row


async def update_application(
    session: AsyncSession, user: User, app_id: uuid.UUID, payload: ApplicationUpdate
) -> JobApplication:
    """Patch mutable fields (status changes go through change_status)."""
    row = await get_owned(session, user, app_id)
    data = payload.model_dump(exclude_unset=True)
    company_name = data.pop("company", None)
    if company_name is not None:
        row.company = await repository.get_or_create_company(session, company_name)
    for field, value in data.items():
        setattr(row, field, value)
    row.updated_at = utcnow()
    await audit_repository.log(
        session, user.id, "tracker.application.update", "application", row.id
    )
    await session.commit()
    await session.refresh(row)
    return row


async def delete_application(session: AsyncSession, user: User, app_id: uuid.UUID) -> None:
    """Delete an application; history/notes/reminders cascade."""
    row = await get_owned(session, user, app_id)
    await audit_repository.log(
        session, user.id, "tracker.application.delete", "application", row.id
    )
    await repository.delete_application(session, row)
    await session.commit()


async def change_status(
    session: AsyncSession, user: User, app_id: uuid.UUID, to_status: ApplicationStatus
) -> JobApplication:
    """Move status and append the history row atomically (one commit)."""
    row = await get_owned(session, user, app_id)
    validate_transition(row.status, to_status)
    from_status = row.status
    row.status = to_status
    row.updated_at = utcnow()
    await repository.add_history(session, row.id, from_status, to_status)
    await audit_repository.log(
        session, user.id, "tracker.application.status", "application", row.id
    )
    await session.commit()
    await session.refresh(row)
    return row


def export_csv(rows: list[JobApplication]) -> str:
    """Render applications as CSV (header + one row per application)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "company",
            "title",
            "status",
            "location",
            "url",
            "source",
            "resume_version",
            "applied_at",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                str(row.id),
                row.company.name,
                row.title,
                row.status.value,
                row.location or "",
                row.url or "",
                row.source or "",
                row.resume_version or "",
                row.applied_at.isoformat() if row.applied_at else "",
                row.created_at.isoformat(),
            ]
        )
    return buf.getvalue()


def due_cutoff(days: int) -> datetime:
    """Cutoff for the due-reminders query."""
    return utcnow() + timedelta(days=days)
