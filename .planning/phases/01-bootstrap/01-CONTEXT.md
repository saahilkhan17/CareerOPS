# Phase 1: Bootstrap (PRD Phase 0) - Context

**Gathered:** 2026-10-12
**Status:** Ready for planning
**Source:** Inline (PRD.md + AGENTS.md + OPENCODE_PROMPTS.md Phase 0 prompt; subagent runtime unavailable)

<domain>
## Phase Boundary

Runnable skeleton: pyproject, compose (PG+Redis only), FastAPI factory with
/health + /ready, pydantic-settings config + .env.example, async SQLAlchemy +
async Alembic, JSON logging with request-ID middleware, Makefile, passing
health-check test. No CI/CD, no app Dockerfile, no deploy config.

## Environment constraint (discovered 2026-10-12)

- Python 3.12.10 + uv present. **Docker is NOT installed** on this machine.
- Consequence: `make services` / live-DB paths cannot be verified here.
  Tests must pass without Docker; DB-dependent paths (/ready OK-path, migrate)
  are code-reviewed + error-path tested, verified live when Docker exists.
</domain>

<decisions>
## Implementation Decisions

### Packaging / deps
- `pyproject.toml` with `uv`-managed venv; dev extras (pytest, ruff, mypy).
  asyncio_mode=auto; ruff line-length 100, target py312; mypy strict.
- Deps locked to PRD stack only: fastapi, uvicorn, pydantic v2, pydantic-settings,
  sqlalchemy[asyncio], asyncpg, alembic. No redis client yet (no app code needs it);
  compose still ships redis per spec.

### App shape
- `app/main.py`: `create_app()` factory; /health (no deps, always 200);
  /ready checks `SELECT 1` on async engine → 200 `{"status":"ready"}` or 503
  in standard error envelope.
- `app/core/config.py`: pydantic-settings `Settings` (app_name, env,
  database_url, redis_url, log_level). JWT settings deferred to Phase 2.
- `app/core/logging.py`: stdlib JSON formatter; `request_id` via ContextVar on
  every record; `configure_logging()` idempotent.
- `app/core/middleware.py`: RequestIdMiddleware (propagate/incoming `X-Request-ID`
  or uuid4) + access log line per request.
- `app/db/session.py`: async engine + `async_session_factory` + `get_session`
  dependency (unused by routers yet — Phase 2). `app/db/base.py`: DeclarativeBase.
- Global handlers: 404 + unhandled Exception → standard error envelope
  `{"error": {"code": ..., "message": ...}}`.

### Migrations
- Alembic async template (`env.py` runs off `app.core.config` + `Base.metadata`);
  one initial empty revision proving the chain. `make migrate` needs live PG.

### Tests
- `tests/test_health.py`: /health 200 shape; 404 envelope shape; /ready DB-down
  → 503 envelope (deterministic, no Docker). Async via httpx ASGITransport.

### the agent's Discretion
- Exact JSON log field set; middleware header name (`X-Request-ID` standard);
  error `code` strings (`not_found`, `service_unavailable`, `internal_error`).
</decisions>

<canonical_refs>
## Canonical References

- `AGENTS.md` — stack, layout, error format, logging, commands, don'ts
- `PRD.md` §6.6 (PLT-1..3, PLT-7), §9–10 (arch, NFRs), §12 Phase 0 acceptance
- `OPENCODE_PROMPTS.md` Phase 0 prompt — deliverable list
</canonical_refs>

<deferred>
## Deferred Ideas

- JWT/refresh/API-key config (Phase 2); redis client + rate limiting (Phase 4/5);
  duration_ms logging (PLT-5, Phase 5); seed data + full README (Phase 6).
</deferred>

---

*Phase: 01-bootstrap*
*Context gathered: 2026-10-12 inline*
