"""Listing/import/runs endpoint tests (sqlite, no Docker, no network)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ingestion import service as ingestion_service
from app.modules.ingestion.sources import RawListing
from tests.conftest import make_user


async def _headers(test_factory: async_sessionmaker[AsyncSession], email: str) -> dict[str, str]:
    _, headers = await make_user(test_factory, email)
    return headers


async def _seed(
    test_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def fetch() -> list[RawListing]:
        return [
            RawListing(
                source="remoteok",
                external_id="1",
                title="Backend Engineer",
                company="Acme",
                location="Remote",
                remote=True,
                salary_min=120000,
                salary_max=160000,
                currency="USD",
                description="Python and FastAPI required.",
            ),
            RawListing(
                source="greenhouse",
                external_id="2",
                title="Designer",
                company="Globex",
                location="Berlin",
                remote=False,
                description="Figma and CSS.",
            ),
        ]

    await ingestion_service.run_ingestion("seed", test_factory, fetcher=fetch)


async def test_import_json_and_csv(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "i1@example.com")

    resp = await client.post(
        "/listings/import",
        json={
            "format": "json",
            "records": [
                {"title": "Backend Engineer", "company": "Acme", "description": "Python required."}
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"fetched": 1, "inserted": 1, "skipped": 0, "errors": 0}

    # Same import again dedupes deterministically.
    again = await client.post(
        "/listings/import",
        json={
            "format": "json",
            "records": [
                {"title": "Backend Engineer", "company": "Acme", "description": "Python required."}
            ],
        },
        headers=headers,
    )
    assert again.json()["inserted"] == 0 and again.json()["skipped"] == 1

    csv_resp = await client.post(
        "/listings/import",
        json={
            "format": "csv",
            "csv_text": "title,company,location\nDev,Globex,Berlin\n",
        },
        headers=headers,
    )
    assert csv_resp.json()["inserted"] == 1

    bad_format = await client.post(
        "/listings/import", json={"format": "json", "records": []}, headers=headers
    )
    assert bad_format.status_code == 400

    bad_csv = await client.post(
        "/listings/import",
        json={"format": "csv", "csv_text": "name,place\nx,y\n"},
        headers=headers,
    )
    assert bad_csv.status_code == 400

    bad_schema = await client.post(
        "/listings/import",
        json={"format": "xml", "records": []},
        headers=headers,
    )
    assert bad_schema.status_code == 422


async def test_list_filters_pagination_and_detail(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "i2@example.com")
    await _seed(test_factory)

    all_resp = await client.get("/listings", headers=headers)
    body = all_resp.json()
    assert body["total"] == 2 and len(body["items"]) == 2
    first = body["items"][0]
    assert set(first) >= {
        "id",
        "source",
        "title",
        "company",
        "skills",
        "match_score",
    }
    assert first["match_score"] is None
    backend = next(i for i in body["items"] if i["title"] == "Backend Engineer")
    assert {s["skill"] for s in backend["skills"]} >= {"Python", "FastAPI"}

    by_source = await client.get("/listings?source=greenhouse", headers=headers)
    assert by_source.json()["total"] == 1

    by_company = await client.get("/listings?company=glob", headers=headers)
    assert by_company.json()["total"] == 1

    by_q = await client.get("/listings?q=designer", headers=headers)
    assert by_q.json()["total"] == 1

    by_remote = await client.get("/listings?remote=true", headers=headers)
    assert by_remote.json()["total"] == 1

    page = await client.get("/listings?limit=1&offset=1", headers=headers)
    assert page.json()["total"] == 2 and len(page.json()["items"]) == 1

    detail = await client.get(f"/listings/{first['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == first["title"]

    from uuid import uuid4

    assert (await client.get(f"/listings/{uuid4()}", headers=headers)).status_code == 404


async def test_min_score_and_match_score_attach(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "i3@example.com")
    await _seed(test_factory)
    await client.put(
        "/profile",
        json={
            "skills": [{"name": "Python", "years": 5}],
            "target_roles": ["Backend Engineer"],
        },
        headers=headers,
    )
    await ingestion_service.auto_match(test_factory)

    scored = await client.get("/listings?min_score=70", headers=headers)
    assert scored.json()["total"] == 1
    item = scored.json()["items"][0]
    assert item["title"] == "Backend Engineer"
    assert item["match_score"] is not None and item["match_score"] >= 70

    unfiltered = await client.get("/listings", headers=headers)
    by_id = {i["id"]: i["match_score"] for i in unfiltered.json()["items"]}
    assert sum(1 for v in by_id.values() if v is not None) == 2

    strict = await client.get("/listings?min_score=100", headers=headers)
    assert strict.json()["total"] == 0


async def test_min_score_is_caller_scoped(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers_a = await _headers(test_factory, "a5@example.com")
    headers_b = await _headers(test_factory, "b5@example.com")
    await _seed(test_factory)
    await client.put(
        "/profile",
        json={"skills": [{"name": "Python", "years": 5}], "target_roles": []},
        headers=headers_a,
    )
    await ingestion_service.auto_match(test_factory)

    mine = await client.get("/listings?min_score=1", headers=headers_a)
    assert mine.json()["total"] >= 1
    # B has no results: shared listings visible, but nothing scored for them.
    theirs = await client.get("/listings?min_score=1", headers=headers_b)
    assert theirs.json()["total"] == 0
    visible = await client.get("/listings", headers=headers_b)
    assert visible.json()["total"] == 2


async def test_runs_ledger(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "i4@example.com")
    await _seed(test_factory)

    runs = await client.get("/ingestion/runs", headers=headers)
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["source"] == "seed"
    assert runs.json()[0]["inserted"] == 2

    by_source = await client.get("/ingestion/runs?source=seed", headers=headers)
    assert len(by_source.json()) == 1
    other = await client.get("/ingestion/runs?source=nope", headers=headers)
    assert other.json() == []


async def test_anonymous_401(client: AsyncClient) -> None:
    assert (await client.get("/listings")).status_code == 401
    assert (
        await client.post("/listings/import", json={"format": "json", "records": []})
    ).status_code == 401


async def test_import_csv_edge_cases(
    client: AsyncClient, test_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await _headers(test_factory, "i5@example.com")

    # Blank rows are skipped; the valid row still lands.
    resp = await client.post(
        "/listings/import",
        json={
            "format": "csv",
            "csv_text": "title,company,location\n,Acme,\nDev,,Berlin\nOps,Globex,Berlin\n",
        },
        headers=headers,
    )
    assert resp.json() == {"fetched": 1, "inserted": 1, "skipped": 0, "errors": 0}

    # No valid rows at all → 400.
    empty = await client.post(
        "/listings/import",
        json={"format": "csv", "csv_text": "title,company\n,\n"},
        headers=headers,
    )
    assert empty.status_code == 400

    # CSV format without csv_text → 400.
    missing = await client.post("/listings/import", json={"format": "csv"}, headers=headers)
    assert missing.status_code == 400
