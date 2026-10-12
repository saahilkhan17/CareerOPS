"""Listing routes: browse, import, ingestion ledger (auth required)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.analytics import repository as analytics_repository
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.ingestion import repository, service
from app.modules.ingestion.models import Listing
from app.modules.ingestion.schemas import (
    ImportIn,
    ImportOut,
    IngestionRunOut,
    ListingOut,
    ListingSkillOut,
    PaginatedListings,
    listing_out,
)
from app.modules.ingestion.sources import RawListing, parse_iso_datetime

router = APIRouter(tags=["listings"])


async def _assemble(session: AsyncSession, user: User, rows: list[Listing]) -> list[ListingOut]:
    """Attach skills + caller scores to listing rows (two batched queries)."""
    ids = [row.id for row in rows]
    skills = await repository.skills_for(session, ids)
    scores = await repository.latest_scores(session, user.id, ids)
    return [
        listing_out(
            row,
            [ListingSkillOut.model_validate(s) for s in skills.get(row.id, [])],
            scores.get(row.id),
        )
        for row in rows
    ]


@router.get("/listings", response_model=PaginatedListings)
async def list_listings(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    source: str | None = None,
    company: str | None = None,
    q: str | None = None,
    remote: bool | None = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedListings:
    """Browse shared market listings; min_score uses my persisted results."""
    items, total = await repository.list_listings(
        session,
        source=source,
        company=company,
        query=q,
        remote=remote,
        min_score=min_score,
        user_id=user.id,
        limit=limit,
        offset=offset,
    )
    return PaginatedListings(
        items=await _assemble(session, user, items),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/listings/import", response_model=ImportOut)
async def import_listings(
    payload: ImportIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportOut:
    """Import listings from JSON records or CSV text (normalized + deduped)."""
    # Any authenticated user may import; listings are shared market data.
    raws: list[RawListing] = []
    if payload.format == "json":
        if not payload.records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="json import needs records",
            )
        for record in payload.records:
            raws.append(
                service.import_raw(
                    record.title,
                    record.company,
                    record.location,
                    record.description,
                    record.url,
                    record.posted_at,
                )
            )
    else:
        if not payload.csv_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="csv import needs csv_text",
            )
        try:
            rows = service.parse_import_csv(payload.csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
        for row in rows:
            raws.append(
                service.import_raw(
                    str(row.get("title")),
                    str(row.get("company")),
                    row.get("location"),
                    row.get("description"),
                    row.get("url"),
                    parse_iso_datetime(row.get("posted_at")),
                )
            )

    async def _fetch() -> list[RawListing]:
        return raws

    if len(raws) > service.MAX_IMPORT_RECORDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"import too large (max {service.MAX_IMPORT_RECORDS} records)",
        )
    stats = await service.run_ingestion_in("import", session, fetcher=_fetch, actor=user.id)
    if stats["inserted"]:
        # Keep the precomputed summary fresh: user imports expect visibility.
        await analytics_repository.rebuild_summary(session)
    return ImportOut(**stats)


@router.get("/listings/{listing_id}", response_model=ListingOut)
async def get_listing(
    listing_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListingOut:
    """Fetch one listing with skills and my latest score."""
    row = await repository.get_listing(session, listing_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return (await _assemble(session, user, [row]))[0]


@router.get("/ingestion/runs", response_model=list[IngestionRunOut])
async def list_runs(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    source: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[IngestionRunOut]:
    """Ingestion ledger, newest first."""
    # Shared operational data; any authenticated user may read it.
    rows = await repository.list_runs(session, source, limit)
    return [IngestionRunOut.model_validate(r) for r in rows]
