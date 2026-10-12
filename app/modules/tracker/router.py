"""Tracker routes: applications, status, history, notes, reminders, export."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.tracker import repository, service
from app.modules.tracker.models import ApplicationStatus, JobApplication
from app.modules.tracker.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    HistoryOut,
    NoteCreate,
    NoteOut,
    PaginatedApplications,
    ReminderCreate,
    ReminderDoneIn,
    ReminderOut,
    StatusChangeIn,
)

router = APIRouter(tags=["applications"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application not found")


async def _owned(session: AsyncSession, user: User, app_id: uuid.UUID) -> JobApplication:
    try:
        return await service.get_owned(session, user, app_id)
    except service.NotFoundError:
        raise _not_found() from None


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobApplication:
    """Create an application (company resolved by name)."""
    return await service.create_application(session, user, payload)


@router.get("/applications", response_model=PaginatedApplications)
async def list_applications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    company: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedApplications:
    """List my applications with filters, sorting, and limit/offset + total."""
    if sort_by not in repository.SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid sort_by: {sort_by}",
        )
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="order must be asc or desc"
        )
    items, total = await repository.list_applications(
        session,
        user.id,
        status=status_filter,
        company=company,
        date_from=date_from,
        date_to=date_to,
        query=q,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    return PaginatedApplications(
        items=[ApplicationOut.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/applications/export.csv")
async def export_csv(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Download all my applications as CSV."""
    items, _ = await repository.list_applications(session, user.id, limit=10000, offset=0)
    body = service.export_csv(items)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="applications.csv"'},
    )


@router.get("/applications/reminders/due", response_model=list[ReminderOut])
async def reminders_due(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=0, le=365)] = 7,
) -> list[ReminderOut]:
    """Undone reminders due within the next `days` days (or overdue)."""
    rows = await repository.due_reminders(session, user.id, service.due_cutoff(days))
    return [ReminderOut.model_validate(r) for r in rows]


@router.get("/applications/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobApplication:
    """Fetch one of my applications."""
    return await _owned(session, user, app_id)


@router.patch("/applications/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: uuid.UUID,
    payload: ApplicationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobApplication:
    """Patch mutable fields (status moves via /status)."""
    try:
        return await service.update_application(session, user, app_id, payload)
    except service.NotFoundError:
        raise _not_found() from None


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Delete an application and its children."""
    try:
        await service.delete_application(session, user, app_id)
    except service.NotFoundError:
        raise _not_found() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/applications/{app_id}/status", response_model=ApplicationOut)
async def change_status(
    app_id: uuid.UUID,
    payload: StatusChangeIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JobApplication:
    """Move status; illegal transitions return 409."""
    try:
        return await service.change_status(session, user, app_id, payload.to_status)
    except service.NotFoundError:
        raise _not_found() from None
    except service.TransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.get("/applications/{app_id}/history", response_model=list[HistoryOut])
async def list_history(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[HistoryOut]:
    """Full status history for one application."""
    await _owned(session, user, app_id)
    rows = await repository.list_history(session, app_id)
    return [HistoryOut.model_validate(r) for r in rows]


@router.post(
    "/applications/{app_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_note(
    app_id: uuid.UUID,
    payload: NoteCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NoteOut:
    """Add a timestamped note."""
    await _owned(session, user, app_id)
    row = await repository.add_note(session, app_id, payload.body)
    await session.commit()
    return NoteOut.model_validate(row)


@router.get("/applications/{app_id}/notes", response_model=list[NoteOut])
async def list_notes(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[NoteOut]:
    """List notes for one application."""
    await _owned(session, user, app_id)
    rows = await repository.list_notes(session, app_id)
    return [NoteOut.model_validate(r) for r in rows]


@router.post(
    "/applications/{app_id}/reminders",
    response_model=ReminderOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_reminder(
    app_id: uuid.UUID,
    payload: ReminderCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReminderOut:
    """Set a follow-up reminder."""
    await _owned(session, user, app_id)
    row = await repository.add_reminder(session, app_id, payload.due_at)
    await session.commit()
    return ReminderOut.model_validate(row)


@router.get("/applications/{app_id}/reminders", response_model=list[ReminderOut])
async def list_reminders(
    app_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ReminderOut]:
    """List reminders for one application."""
    await _owned(session, user, app_id)
    rows = await repository.list_reminders(session, app_id)
    return [ReminderOut.model_validate(r) for r in rows]


@router.patch("/applications/{app_id}/reminders/{reminder_id}", response_model=ReminderOut)
async def set_reminder_done(
    app_id: uuid.UUID,
    reminder_id: uuid.UUID,
    payload: ReminderDoneIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReminderOut:
    """Flip a reminder's done flag (scoped to my applications)."""
    await _owned(session, user, app_id)
    row = await repository.get_reminder(session, user.id, reminder_id)
    if row is None or row.application_id != app_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder not found")
    row.done = payload.done
    await session.commit()
    return ReminderOut.model_validate(row)
