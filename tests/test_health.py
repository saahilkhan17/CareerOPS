"""Phase 1 health/readiness/error-envelope tests (no live services needed)."""

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_request_id_propagated(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"


async def test_request_id_minted(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0


async def test_not_found_envelope(client: AsyncClient) -> None:
    resp = await client.get("/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)


async def test_ready_db_down_returns_503_envelope(client: AsyncClient) -> None:
    # No Postgres in this environment, so readiness must fail closed
    # with the standard envelope (never a traceback or bare 500).
    resp = await client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"]["code"] == "service_unavailable"


async def test_openapi_lists_health_and_ready(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/health" in paths
    assert "/ready" in paths
