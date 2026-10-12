# Intel: Decisions (synthesized from PRD, AGENTS.md, OPENCODE_PROMPTS.md)

Source precedence: SPEC (AGENTS.md) > PRD (PRD.md) > DOC (OPENCODE_PROMPTS.md).
`deve/` harness docs excluded — process governance, not product scope.

## Locked decisions

1. **Stack is fixed**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async,
   Alembic, PostgreSQL 16 (+pgvector later), Redis, Celery + Celery Beat,
   JWT access+refresh, Pytest + pytest-asyncio + httpx, Ruff, mypy, uv or pip-tools.
   (SPEC §Stack — do not swap without asking)
2. **Layered architecture**: routers → services → repositories → models.
   Routers never touch the DB. Pydantic schemas separate from ORM models.
3. **Docker Compose runs ONLY Postgres + Redis** for local dev. No app Dockerfile,
   no CI/CD, no cloud/K8s, no Prometheus/Grafana (separate DevOps project).
4. **Config via environment variables** (pydantic-settings); ship `.env.example`; never commit secrets.
5. **Every schema change = Alembic migration**; never edit applied migrations.
6. **Error format**: `{"error": {"code": "...", "message": "..."}}`; proper HTTP codes;
   `limit`/`offset` + total pagination; idempotent writes where relevant.
7. **Structured JSON logging with request ID**; `/health` and `/ready` endpoints.
8. **Match scoring is deterministic, no LLM in the numeric path** (PRD MAT-4).
   Optional LLM explanation is behind a feature flag + interface (MAT-7).
9. **Ingestion sources restricted to legitimate endpoints**: Greenhouse/Lever public
   boards, one public jobs API, CSV/JSON import. No scraping of LinkedIn/Naukri/Indeed.
   Respect robots.txt and rate limits.
10. **Quality bar**: ≥80% coverage; `make lint test` green before every commit;
    type hints everywhere; ADRs in `docs/DECISIONS.md`; ideas to `docs/BACKLOG.md`.
