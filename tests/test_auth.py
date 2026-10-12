"""Auth endpoint tests (sqlite, no Docker)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import PASSWORD, make_user


async def test_register_ok(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register", json={"email": "a@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "id" in body and "password" not in body and "password_hash" not in body


async def test_register_duplicate_409(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": PASSWORD}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_register_duplicate_case_insensitive(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "Case@Example.com", "password": PASSWORD})
    resp = await client.post(
        "/auth/register", json={"email": "case@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 409


async def test_register_bad_email_422(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json={"email": "not-an-email", "password": PASSWORD})
    assert resp.status_code == 422


async def test_register_short_password_422(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json={"email": "b@example.com", "password": "short"})
    assert resp.status_code == 422


async def test_register_long_password_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register", json={"email": "c@example.com", "password": "x" * 73}
    )
    assert resp.status_code == 422


async def test_login_ok(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "l@example.com", "password": PASSWORD})
    resp = await client.post("/auth/login", json={"email": "l@example.com", "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


async def test_login_wrong_password_401(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "w@example.com", "password": PASSWORD})
    resp = await client.post(
        "/auth/login", json={"email": "w@example.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_login_unknown_email_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401


async def test_me_ok_and_anonymous_401(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, headers = await make_user(test_factory, "me@example.com")
    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"

    anon = await client.get("/auth/me")
    assert anon.status_code == 401
    assert anon.json()["error"]["code"] == "unauthorized"


async def test_me_garbage_bearer_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401


async def test_refresh_rotation_kills_old(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "r@example.com", "password": PASSWORD})
    login = (
        await client.post("/auth/login", json={"email": "r@example.com", "password": PASSWORD})
    ).json()
    first_refresh = login["refresh_token"]

    rotated = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first_refresh

    reuse = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert reuse.status_code == 401

    bad = await client.post("/auth/refresh", json={"refresh_token": "nope" + "x" * 30})
    assert bad.status_code == 401


async def test_logout_idempotent(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "o@example.com", "password": PASSWORD})
    login = (
        await client.post("/auth/login", json={"email": "o@example.com", "password": PASSWORD})
    ).json()
    refresh = login["refresh_token"]

    assert (await client.post("/auth/logout", json={"refresh_token": refresh})).status_code == 204
    # Refresh dead after logout.
    assert (await client.post("/auth/refresh", json={"refresh_token": refresh})).status_code == 401
    # Logging out twice (or with garbage) is still 204.
    assert (await client.post("/auth/logout", json={"refresh_token": refresh})).status_code == 204
    assert (await client.post("/auth/logout", json={"refresh_token": "x" * 40})).status_code == 204


async def test_api_key_lifecycle(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, headers = await make_user(test_factory, "k@example.com")

    created = await client.post("/auth/api-keys", json={"name": "laptop"}, headers=headers)
    assert created.status_code == 201
    key = created.json()["key"]
    assert key.startswith("co_")
    key_id = created.json()["id"]

    listed = await client.get("/auth/api-keys", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "key" not in listed.json()[0]  # plaintext shown exactly once

    via_key = await client.get("/auth/me", headers={"X-API-Key": key})
    assert via_key.status_code == 200

    assert (await client.delete(f"/auth/api-keys/{key_id}", headers=headers)).status_code == 204
    dead = await client.get("/auth/me", headers={"X-API-Key": key})
    assert dead.status_code == 401

    missing = await client.delete(f"/auth/api-keys/{key_id}", headers=headers)
    assert missing.status_code == 404


async def test_api_key_bad_header_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me", headers={"X-API-Key": "co_bogus"})
    assert resp.status_code == 401
