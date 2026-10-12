"""Auth persistence: users, refresh tokens, API keys. No business logic here."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.auth.models import ApiKey, RefreshToken, User


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def create_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> RefreshToken:
    row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(session: AsyncSession, row: RefreshToken) -> None:
    row.revoked_at = utcnow()
    await session.flush()


async def create_api_key(
    session: AsyncSession, user_id: uuid.UUID, key_hash: str, name: str
) -> ApiKey:
    row = ApiKey(user_id=user_id, key_hash=key_hash, name=name)
    session.add(row)
    await session.flush()
    return row


async def list_api_keys(session: AsyncSession, user_id: uuid.UUID) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_key(
    session: AsyncSession, user_id: uuid.UUID, key_id: uuid.UUID
) -> ApiKey | None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def touch_api_key(session: AsyncSession, row: ApiKey) -> None:
    row.last_used_at = utcnow()
    await session.flush()
