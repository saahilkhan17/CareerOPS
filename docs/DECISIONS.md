# Design Decisions (ADR-style, short)

## ADR-0001: Fixed stack, no swapping without asking (2026-10-12)

Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 async / Alembic / PG16 /
Redis / Celery+Beat / JWT / Pytest+httpx / Ruff / mypy / uv.
Chosen because it is the standard hiring signal for Python backend roles and
covers async I/O, migrations, workers, and caching — everything the PRD needs.
Status: accepted.

## ADR-0002: Deterministic match score, LLM kept out of the number (2026-10-12)

MAT-4/MAT-7: scoring is a weighted formula (required/p preferred coverage,
experience fit, title similarity); the optional LLM layer only writes
suggestions. Rationale: opaque scores are untestable and untrustworthy;
determinism enables precision/recall measurement over the labeled JD set.
Applies in Phase 3. Status: accepted.

## ADR-0003: Bootstrap verified without Docker on this machine (2026-10-12)

Docker is not installed here, so `make services`, live `migrate`, and the
`/ready` 200-path cannot run locally yet. Mitigation: `/ready` fails closed
with the standard 503 envelope (tested); Alembic chain verified offline via
`alembic history`; compose file ships PG16+Redis for machines with Docker.
Re-verify live paths once Docker exists. Status: accepted, revisit on Phase 2.

Note: smoke test showed *something* listens on localhost:5432 (got a real PG
auth error, not a refused connection) — /ready correctly failed closed with
the 503 envelope. Live 200-path still unverified.

## ADR-0004: Stdlib JSON logging instead of structlog (2026-10-12)

Phase 1 needs JSON lines + request ID only. A small stdlib formatter avoids a
dependency; revisit if structured-context needs grow (Phase 5). Status: accepted.

## ADR-0005: `make lint` scopes to product code (2026-10-12)

`ruff`/`mypy` run over `app tests alembic` only. Rationale: `deve/` and
`.harness/` are pre-existing process tooling with their own Taskfile lint and
older style (they fail current ruff rules); touching them is out of scope and
AGENTS.md says ask before changing unrelated files. Status: accepted.
