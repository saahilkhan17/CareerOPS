"""Audit persistence. Services log before their own commits."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


async def log(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None = None,
) -> AuditLog:
    """Append an audit row (flushed; the caller commits)."""
    row = AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id)
    session.add(row)
    await session.flush()
    return row
