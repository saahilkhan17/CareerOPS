"""Edge-case tests: expiry, malformed tokens, factory caching, 404 branches."""

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import security
from app.core.time import utcnow
from app.db import session as session_module
from app.modules.auth import repository as auth_repo
from app.modules.auth.service import auth_secret
from tests.conftest import PASSWORD, make_user


async def test_expired_refresh_is_rejected_and_revoked(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    user, _ = await make_user(test_factory, "exp@example.com")
    async with test_factory() as session:
        row = await auth_repo.create_refresh_token(
            session,
            user.id,
            security.sha256_hex("expired-token-" + "x" * 30),
            utcnow() - timedelta(seconds=1),
        )
        await session.commit()
        row_id = row.id

    resp = await client.post("/auth/refresh", json={"refresh_token": "expired-token-" + "x" * 30})
    assert resp.status_code == 401

    async with test_factory() as session:
        fetched = await auth_repo.get_refresh_token(
            session, security.sha256_hex("expired-token-" + "x" * 30)
        )
        assert fetched is not None and fetched.id == row_id
        assert fetched.revoked_at is not None


async def test_auth_secret_cached() -> None:
    first = auth_secret()
    assert auth_secret() == first


async def test_decode_rejects_wrong_type_and_bad_sub() -> None:
    import jwt

    secret = auth_secret()
    wrong_type = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh"}, secret, algorithm="HS256"
    )
    assert security.decode_access_token(wrong_type, secret) is None
    bad_sub = jwt.encode({"sub": "not-a-uuid", "type": "access"}, secret, algorithm="HS256")
    assert security.decode_access_token(bad_sub, secret) is None
    assert security.decode_access_token("junk", secret) is None


async def test_session_factories_cached_without_io() -> None:
    assert session_module.get_engine() is session_module.get_engine()
    assert session_module.get_session_factory() is session_module.get_session_factory()


async def test_api_key_without_prefix_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me", headers={"X-API-Key": "junk-no-prefix"})
    assert resp.status_code == 401


async def test_reminder_done_missing_404(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, headers = await make_user(test_factory, "r404@example.com")
    created = (
        await client.post(
            "/applications",
            json={"company": "Acme", "title": "Dev"},
            headers=headers,
        )
    ).json()
    resp = await client.patch(
        f"/applications/{created['id']}/reminders/{uuid.uuid4()}",
        json={"done": True},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_login_trims_case_insensitive_email(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "Mixed@Example.com", "password": PASSWORD})
    resp = await client.post(
        "/auth/login", json={"email": "  MIXED@example.com  ", "password": PASSWORD}
    )
    assert resp.status_code == 200
