"""Shared fixtures: in-process ASGI client + sqlite DB (no network, no Docker)."""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.modules.analytics.models  # noqa: F401  (register analytics tables)
import app.modules.audit.models  # noqa: F401  (register audit table)
import app.modules.auth.models  # noqa: F401  (register auth tables)
import app.modules.ingestion.models  # noqa: F401  (register ingestion tables)
import app.modules.match.models  # noqa: F401  (register match tables)
import app.modules.tracker.models  # noqa: F401  (register tracker tables)
from app.core import security
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import User

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _fake_redis() -> Iterator[None]:
    """Isolate every test on a fresh in-memory Redis (no server needed)."""
    from fakeredis.aioredis import FakeRedis

    from app.core import redis_client

    redis_client.set_redis_client(FakeRedis(decode_responses=True))
    yield
    redis_client.set_redis_client(None)


@pytest_asyncio.fixture
async def test_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Function-scoped sqlite DB (single shared :memory: connection)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    test_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """HTTP client with get_session overridden to the sqlite test DB."""
    app = create_app()

    async def override() -> AsyncIterator[AsyncSession]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def make_user(
    test_factory: async_sessionmaker[AsyncSession], email: str
) -> tuple[User, dict[str, str]]:
    """Create a user + valid Bearer headers (helper, not a fixture)."""
    async with test_factory() as session:
        user = await auth_repo.create_user(session, email, security.hash_password(PASSWORD))
        await session.commit()
        access = security.create_access_token(user.id, _test_secret())
        await session.refresh(user)
        return user, {"Authorization": f"Bearer {access}"}


def _test_secret() -> str:
    from app.modules.auth.service import auth_secret

    return auth_secret()
