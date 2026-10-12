"""Auth business logic: registration, credentials, token rotation, API keys."""

import logging
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.time import utcnow
from app.modules.auth import repository
from app.modules.auth.models import ApiKey, User

logger = logging.getLogger("careerops.auth")

_secret: str | None = None


class EmailTakenError(Exception):
    """Registration attempted with an existing email."""


def auth_secret() -> str:
    """Return the JWT secret, minting a per-process one when unconfigured."""
    global _secret
    if _secret is not None:
        return _secret
    configured = get_settings().auth_secret_key
    if configured:
        _secret = configured
    else:
        _secret = secrets.token_urlsafe(32)
        logger.warning(
            "AUTH_SECRET_KEY unset: using a per-process secret; "
            "access tokens will not survive restarts. Set AUTH_SECRET_KEY in prod."
        )
    return _secret


async def register(session: AsyncSession, email: str, password: str) -> User:
    """Create a user; raise EmailTakenError when the email exists."""
    lowered = email.strip().lower()
    if await repository.get_user_by_email(session, lowered) is not None:
        raise EmailTakenError(lowered)
    user = await repository.create_user(session, lowered, security.hash_password(password))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise EmailTakenError(lowered) from None
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Return the user when credentials match, else None (no reason given)."""
    user = await repository.get_user_by_email(session, email.strip().lower())
    if user is None:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> tuple[str, str]:
    """Issue (access JWT, opaque refresh token) and persist the refresh row."""
    access = security.create_access_token(user.id, auth_secret())
    refresh = security.mint_opaque_token()
    await repository.create_refresh_token(
        session,
        user.id,
        security.sha256_hex(refresh),
        utcnow() + security.REFRESH_TOKEN_TTL,
    )
    await session.commit()
    return access, refresh


async def rotate_refresh(session: AsyncSession, refresh_token: str) -> tuple[User, str, str] | None:
    """Consume a refresh token: revoke it, return (user, new access, new refresh).

    Returns None for unknown, revoked, or expired tokens (expired rows are
    revoked opportunistically).
    """
    row = await repository.get_refresh_token(session, security.sha256_hex(refresh_token))
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= utcnow():
        await repository.revoke_refresh_token(session, row)
        await session.commit()
        return None
    user = await repository.get_user_by_id(session, row.user_id)
    if user is None:
        return None
    await repository.revoke_refresh_token(session, row)
    access = security.create_access_token(user.id, auth_secret())
    new_refresh = security.mint_opaque_token()
    await repository.create_refresh_token(
        session,
        user.id,
        security.sha256_hex(new_refresh),
        utcnow() + security.REFRESH_TOKEN_TTL,
    )
    await session.commit()
    return user, access, new_refresh


async def logout(session: AsyncSession, refresh_token: str) -> None:
    """Revoke a refresh token; unknown tokens are ignored (idempotent)."""
    row = await repository.get_refresh_token(session, security.sha256_hex(refresh_token))
    if row is None or row.revoked_at is not None:
        return
    await repository.revoke_refresh_token(session, row)
    await session.commit()


async def create_api_key(session: AsyncSession, user: User, name: str) -> tuple[ApiKey, str]:
    """Create an API key; return (row, plaintext key shown exactly once)."""
    key = security.mint_api_key()
    row = await repository.create_api_key(session, user.id, security.sha256_hex(key), name)
    await session.commit()
    return row, key


async def list_api_keys(session: AsyncSession, user: User) -> list[ApiKey]:
    """List the user's active (non-revoked) API keys."""
    return await repository.list_api_keys(session, user.id)


async def revoke_api_key(session: AsyncSession, user: User, key_id: uuid.UUID) -> bool:
    """Revoke one of the user's keys; False when it does not exist."""
    row = await repository.get_api_key(session, user.id, key_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = utcnow()
    await session.commit()
    return True


async def resolve_api_key(session: AsyncSession, key: str) -> User | None:
    """Return the owning user for a live API key, else None."""
    if not key.startswith(security.API_KEY_PREFIX):
        return None
    row = await repository.get_api_key_by_hash(session, security.sha256_hex(key))
    if row is None or row.revoked_at is not None:
        return None
    await repository.touch_api_key(session, row)
    await session.commit()
    return await repository.get_user_by_id(session, row.user_id)
