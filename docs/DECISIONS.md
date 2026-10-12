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

## ADR-0006: coverage needs greenlet concurrency for async SQLAlchemy (2026-10-12)

With plain coverage settings, every line after the first DB `await` in a
coroutine reported as missed (suite showed 79% while all tests passed).
`[tool.coverage.run] concurrency = ["greenlet", "thread"]` restored true
numbers (97.7%). Caveat: the greenlet tracer still misreports 2 early-return
lines in `auth_secret()` (28-29) — proven executed by a passing equality
assertion, so this is a measurement artifact, not dead code. Status: accepted.

## ADR-0007: strict terminal states, no reapply edges (2026-10-12)

rejected/withdrawn have no outgoing edges; same-status moves 409. Rationale:
matches the PRD's linear diagram and keeps the machine auditable; reapply
(rejected→applied) is real but deferred — reopen via BACKLOG if wanted.
Pure `validate_transition()` holds the map; tests pin the edge count (13).
Status: accepted.

## ADR-0008: sqlite-for-tests, naive-UTC clock, Annotated dependencies (2026-10-12)

No Docker on this machine, so integration tests run on aiosqlite (dev-only
dep) with `StaticPool` over `:memory:`; PG-only paths (live migrate, native
UUID) are hand-written in the migration and re-verified when Docker exists.
All timestamps naive UTC via `utcnow()` (consistent on sqlite and on PG
`timestamptz` with UTC server TZ). Route signatures use
`Annotated[X, Depends(...)]` (B008-clean, modern FastAPI style). Status: accepted.

## ADR-0009: match scoring formula + measured extraction quality (2026-10-12)

score = round(100 * Σ(w·c)/Σw), weights required 0.5 / preferred 0.2 /
experience 0.2 / title 0.1 (config, normalized by sum). Components: required
coverage (1.0 if none stated), preferred coverage (1.0 if none), experience =
min(profile_max_years/min_years, 1) (1.0 if no minimum), title = overlap
coefficient vs best target role on stopword-stripped tokens (0.5 neutral when
title or roles missing). Missing data is neutral, never punishing.
Extraction measured over 20 labeled JDs (`tests/fixtures/jds/labeled.json`):
**precision 1.000, recall 1.000** (micro-averaged, required/preferred splits
exact on all 20). LLM explanation lives behind `match_llm_enabled` + the
`Explainer` seam and provably cannot move the number (flag-matrix test).
MAT-8 (pgvector) deferred to v2 — no vector infra in this phase's scope.
Status: accepted.

