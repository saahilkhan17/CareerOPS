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

## ADR-0010: RemoteOK as third ingestion source (2026-10-12)

PRD §15 Q1 decided: RemoteOK over Adzuna — Adzuna needs signup credentials
(bad for local dev, fixtures, demo); RemoteOK serves public JSON with no auth.
Revisit if its terms/API change. Greenhouse board→company and Lever
slug→company come from settings maps (their public APIs carry no company
name); empty maps are legal (tasks record zero-fetch runs).

## ADR-0011: Celery tested without a broker (2026-10-12)
No Redis here, so tasks are thin sync wrappers over async services that take
an explicit session factory; the suite drives services directly on sqlite and
asserts task/beat wiring (names, autoretry, schedule) on the Celery app
object. respx mocks all HTTP; unit tests pin retry/backoff/throttle behavior
(including the fix that 4xx from raise_for_status must NOT enter the retry
loop). Live worker/beat verification needs Redis (compose ships it).

## ADR-0012: analytics performance, measured on sqlite (2026-10-12)

EXPLAIN QUERY PLAN over 2000 listings (sqlite, ad-hoc script, since removed):
live GROUP BY over the skills⋈listings join = SCAN 2000 skill rows + covering
index lookups + two TEMP B-TREEs at 1.68 ms mean; summary-table read = SCAN 8
rows + TEMP B-TREEs at 0.77 ms mean (~2.2×, and the gap widens with scale
since the summary is bounded by days×skills, not postings). Endpoint bench
(scripts/bench.py, 50 apps + 300 listings, TestClient + sqlite + fakeredis):
health 3.1 ms, apps list 8.8–9.2 ms, match ~10 ms, listings ~13 ms,
skills/top cold 8.8 ms vs warm 5.7 ms, my-gap 6.2 ms. Full table in
docs/PERFORMANCE.md. PG/Redis numbers pending Docker; summary tables chosen
over materialized views so the mechanism is testable on sqlite.
Status: accepted.

## ADR-0013: hardening trade-offs (2026-10-12)

Redis-backed per-identity rate limiting (JWT sub → key hash → IP, fixed 60s
window, 429 envelope + Retry-After) and JSON cache both fail open when Redis
is down — availability over strictness, logged, tested with a broken client.
Audit rows are written by services before their own commits (one commit per
action, no phantom rows on rollback). RequestValidationError maps to a 422
envelope with sanitized details (raw pydantic ctx holds exception objects and
is not JSON-safe). duration_ms rides the log record as a real field, not just
message text. Status: accepted.

## ADR-0014: Phase 6 security pass (2026-10-12)

- pip-audit over the venv: no known vulnerabilities (CareerOps itself is
  local-only, unauditable by PyPI — expected).
- Secrets scan: full git history + worktree checked for sk-/ghp_/ASIA and
  quoted password/token assignments — clean. Only matches are the scanner's
  own documentation and test fixture passwords (not real secrets). Demo
  credentials (demo@careerops.dev / demo1234) are documented demo-only.
- CORS allowlist from settings (localhost:3000/8000 default), credentials on.
- Validation review: lengths capped (passwords 8–72, notes ≤5000, imports
  ≤2000 records → 400); URLs stay plain strings (no false rejects); emails
  use EmailStr (note: special-use domains like .local are rejected by
  email-validator — demo uses .dev).
- Seeded demo user is demo@careerops.dev: .local fails EmailStr validation
  (caught by a live 422 while capturing README examples).
Status: accepted.

## ADR-0015: vanilla dashboard, no backend changes (2026-10-12)

Dashboard built on explicit request (was a PRD non-goal): plain
HTML/CSS/JS in `dashboard/`, no framework, no build step, no new backend
dependencies — CORS already allowed :3000, so zero API changes were needed.
Every server string renders escaped (XSS); endpoint coverage verified by
contract review against the routers plus `node --check` (`make lint-js`).
Status: accepted.

