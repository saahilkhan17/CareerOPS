"""Tracker endpoint tests incl. cross-user isolation (sqlite, no Docker)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import make_user


def app_payload(**over: object) -> dict[str, object]:
    base: dict[str, object] = {"company": "Acme", "title": "Backend Engineer"}
    base.update(over)
    return base


async def _authed_client(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession], email: str
) -> dict[str, str]:
    _, headers = await make_user(test_factory, email)
    return headers


async def test_create_and_get(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t1@example.com")
    resp = await client.post("/applications", json=app_payload(), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "saved"
    assert body["company"]["name"] == "Acme"

    got = await client.get(f"/applications/{body['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["title"] == "Backend Engineer"

    history = await client.get(f"/applications/{body['id']}/history", headers=headers)
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["from_status"] is None and rows[0]["to_status"] == "saved"


async def test_create_invalid_status_422(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t2@example.com")
    resp = await client.post("/applications", json=app_payload(status="hired"), headers=headers)
    assert resp.status_code == 422


async def test_company_deduped(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t3@example.com")
    a = (await client.post("/applications", json=app_payload(), headers=headers)).json()
    b = (
        await client.post("/applications", json=app_payload(title="Frontend Dev"), headers=headers)
    ).json()
    assert a["company"]["id"] == b["company"]["id"]


async def test_patch_and_delete(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t4@example.com")
    created = (await client.post("/applications", json=app_payload(), headers=headers)).json()

    patched = await client.patch(
        f"/applications/{created['id']}",
        json={"title": "Senior Backend", "company": "Globex"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Senior Backend"
    assert patched.json()["company"]["name"] == "Globex"

    assert (
        await client.delete(f"/applications/{created['id']}", headers=headers)
    ).status_code == 204
    assert (await client.get(f"/applications/{created['id']}", headers=headers)).status_code == 404


async def test_status_happy_path_and_history_growth(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t5@example.com")
    created = (await client.post("/applications", json=app_payload(), headers=headers)).json()
    app_id = created["id"]

    for target in ("applied", "interview", "offer"):
        resp = await client.post(
            f"/applications/{app_id}/status",
            json={"to_status": target},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == target

    history = (await client.get(f"/applications/{app_id}/history", headers=headers)).json()
    assert [h["to_status"] for h in history] == [
        "saved",
        "applied",
        "interview",
        "offer",
    ]
    assert history[1]["from_status"] == "saved"


async def test_status_illegal_409(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t6@example.com")
    created = (await client.post("/applications", json=app_payload(), headers=headers)).json()

    resp = await client.post(
        f"/applications/{created['id']}/status",
        json={"to_status": "offer"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"

    same = await client.post(
        f"/applications/{created['id']}/status",
        json={"to_status": "saved"},
        headers=headers,
    )
    assert same.status_code == 409


async def test_notes_add_and_list(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t7@example.com")
    created = (await client.post("/applications", json=app_payload(), headers=headers)).json()

    added = await client.post(
        f"/applications/{created['id']}/notes",
        json={"body": "reached out on LinkedIn"},
        headers=headers,
    )
    assert added.status_code == 201

    listed = await client.get(f"/applications/{created['id']}/notes", headers=headers)
    assert [n["body"] for n in listed.json()] == ["reached out on LinkedIn"]

    too_long = await client.post(
        f"/applications/{created['id']}/notes",
        json={"body": "x" * 5001},
        headers=headers,
    )
    assert too_long.status_code == 422


async def test_reminders_add_list_done_due(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t8@example.com")
    created = (await client.post("/applications", json=app_payload(), headers=headers)).json()
    app_id = created["id"]

    past = await client.post(
        f"/applications/{app_id}/reminders",
        json={"due_at": "2020-01-01T00:00:00"},
        headers=headers,
    )
    assert past.status_code == 201
    future = await client.post(
        f"/applications/{app_id}/reminders",
        json={"due_at": "2999-01-01T00:00:00"},
        headers=headers,
    )
    assert future.status_code == 201

    listed = await client.get(f"/applications/{app_id}/reminders", headers=headers)
    assert len(listed.json()) == 2

    due = await client.get("/applications/reminders/due", headers=headers)
    assert [r["id"] for r in due.json()] == [past.json()["id"]]

    done = await client.patch(
        f"/applications/{app_id}/reminders/{past.json()['id']}",
        json={"done": True},
        headers=headers,
    )
    assert done.json()["done"] is True
    due_after = await client.get("/applications/reminders/due", headers=headers)
    assert due_after.json() == []


async def test_list_filters_sort_pagination(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t9@example.com")
    await client.post(
        "/applications", json=app_payload(company="Acme", title="Zebra Role"), headers=headers
    )
    await client.post(
        "/applications",
        json=app_payload(company="Globex", title="Alpha Role"),
        headers=headers,
    )
    applied = (
        await client.post(
            "/applications",
            json=app_payload(company="Acme", title="Mid Role", status="applied"),
            headers=headers,
        )
    ).json()
    void = await client.post(
        "/applications", json=app_payload(company="Acme", title="Zzz"), headers=headers
    )
    assert void.status_code == 201

    by_status = await client.get("/applications?status=applied", headers=headers)
    assert by_status.json()["total"] == 1
    assert by_status.json()["items"][0]["id"] == applied["id"]

    by_company = await client.get("/applications?company=glob", headers=headers)
    assert by_company.json()["total"] == 1

    by_q = await client.get("/applications?q=zebra", headers=headers)
    assert by_q.json()["total"] == 1

    sorted_resp = await client.get("/applications?sort_by=title&order=asc", headers=headers)
    titles = [i["title"] for i in sorted_resp.json()["items"]]
    assert titles == sorted(titles)

    page1 = await client.get("/applications?limit=2&offset=0", headers=headers)
    assert page1.json()["total"] == 4
    assert len(page1.json()["items"]) == 2
    page2 = await client.get("/applications?limit=2&offset=2", headers=headers)
    assert len(page2.json()["items"]) == 2
    ids1 = {i["id"] for i in page1.json()["items"]}
    ids2 = {i["id"] for i in page2.json()["items"]}
    assert not ids1 & ids2

    bad_sort = await client.get("/applications?sort_by=hacked", headers=headers)
    assert bad_sort.status_code == 400
    bad_order = await client.get("/applications?order=sideways", headers=headers)
    assert bad_order.status_code == 400


async def test_list_date_range(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t10@example.com")
    await client.post("/applications", json=app_payload(), headers=headers)

    past = await client.get(
        "/applications?date_from=2020-01-01T00:00:00&date_to=2021-01-01T00:00:00",
        headers=headers,
    )
    assert past.json()["total"] == 0

    now = await client.get("/applications?date_from=2020-01-01T00:00:00", headers=headers)
    assert now.json()["total"] == 1


async def test_export_csv(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _authed_client(client, test_factory, "t11@example.com")
    await client.post("/applications", json=app_payload(), headers=headers)

    resp = await client.get("/applications/export.csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().splitlines()
    assert lines[0].split(",")[:4] == ["id", "company", "title", "status"]
    assert len(lines) == 2
    assert "Acme" in lines[1] and "Backend Engineer" in lines[1]


async def test_anonymous_401(client: AsyncClient) -> None:
    assert (await client.get("/applications")).status_code == 401
    assert (await client.post("/applications", json=app_payload())).status_code == 401


async def test_cross_user_isolation(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers_a = await _authed_client(client, test_factory, "alice@example.com")
    headers_b = await _authed_client(client, test_factory, "bob@example.com")

    created = (await client.post("/applications", json=app_payload(), headers=headers_a)).json()
    app_id = created["id"]

    # B sees nothing of A's data (404 both directions, empty lists).
    assert (await client.get(f"/applications/{app_id}", headers=headers_b)).status_code == 404
    assert (
        await client.patch(f"/applications/{app_id}", json={"title": "Hijack"}, headers=headers_b)
    ).status_code == 404
    assert (
        await client.post(
            f"/applications/{app_id}/status",
            json={"to_status": "applied"},
            headers=headers_b,
        )
    ).status_code == 404
    assert (await client.get(f"/applications/{app_id}/notes", headers=headers_b)).status_code == 404
    assert (
        await client.post(f"/applications/{app_id}/notes", json={"body": "x"}, headers=headers_b)
    ).status_code == 404
    assert (await client.delete(f"/applications/{app_id}", headers=headers_b)).status_code == 404
    assert (await client.get("/applications", headers=headers_b)).json()["total"] == 0
    assert (await client.get("/applications/export.csv", headers=headers_b)).text.count(
        "Backend Engineer"
    ) == 0

    # A unaffected.
    assert (await client.get(f"/applications/{app_id}", headers=headers_a)).status_code == 200
