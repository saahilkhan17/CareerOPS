# CareerOps — OpenCode Prompt Playbook

How to use: put `AGENTS.md` in the repo root, start OpenCode there, then paste ONE prompt at a time.
Review the diff and run `make lint test` yourself after every phase. Commit only when green.
Scope note: this is a pure backend project. No app Docker image, CI/CD, cloud deploy or monitoring stack (separate DevOps track).
Tip: use OpenCode's plan mode first, then switch to build mode once you approve the plan.

---

## Phase 0 — Bootstrap (day 1)

```
Read AGENTS.md fully. Then bootstrap the CareerOps repo exactly per the folder layout and stack in it.

Deliver:
- pyproject.toml with deps and ruff/mypy/pytest config
- docker-compose.yml that runs ONLY Postgres and Redis for local development (no Dockerfile for the app)
- app/main.py with FastAPI app factory, /health and /ready endpoints
- core/config.py using pydantic-settings, .env.example
- Async SQLAlchemy session setup and Alembic initialised for async
- Structured JSON logging with request-ID middleware
- Makefile with the commands listed in AGENTS.md
- tests/ with a passing health-check test
- NO CI/CD pipeline, NO app Dockerfile, NO deployment config (out of scope per AGENTS.md)
- README skeleton and docs/DECISIONS.md, docs/BACKLOG.md

First show me your plan as a file list. Do not write code until I approve.
```

## Phase 1 — Auth + Tracker (weeks 1–1.5)

```
Implement Phase 1: auth and the application tracker. Plan first, wait for approval.

Auth module:
- Register, login, refresh, logout. Passwords hashed with argon2 or bcrypt.
- JWT access (15 min) + refresh tokens (rotating, stored hashed in DB, revocable).
- `get_current_user` dependency.

Tracker module:
- Models: Company, JobApplication, StatusHistory, Note, Reminder. All scoped to user_id.
- Status state machine: saved → applied → oa → interview → offer | rejected | withdrawn.
  Illegal transitions return 409 with a clear error. Every transition writes a StatusHistory row in the same transaction.
- Endpoints: CRUD for applications, change-status, add note, set reminder,
  list with filters (status, company, date range, text search) + pagination + sorting.
- CSV export endpoint.
- Alembic migration(s) for all tables, with sensible indexes (user_id+status, user_id+created_at).

Tests: unit tests for the state machine, integration tests for every endpoint including
auth failures and cross-user access (user A must not see user B's data).
Finish with `make lint test` output and an updated README "API overview" section.
```

## Phase 2 — JD Match Scoring (weeks 2–3)

```
Implement Phase 2: the match-scoring module. Plan first, wait for approval.

- Profile model: user's skills (with optional years/level), target roles, education, preferences.
- Skill taxonomy: a versioned JSON/CSV file of canonical skills + aliases (e.g. "postgres" → "PostgreSQL").
  Put it in app/modules/match/data/ and keep it easy to extend.
- Extraction service: pull skills, required vs preferred (heuristic on phrases like "must have"/"nice to have"),
  min years of experience, and seniority signals from raw JD text.
- Scoring service (deterministic, no LLM): weighted score 0–100 =
  required-skill coverage, preferred-skill coverage, experience fit, role-title similarity.
  Weights live in config. Return a breakdown, matched skills, missing skills.
- POST /match (paste JD text) and POST /match/{application_id}. Persist results in a MatchResult table.
- Optional, behind a feature flag and an interface (so it's mockable): LLM explanation service that turns the
  breakdown into resume-improvement suggestions. The numeric score must NEVER depend on the LLM.

Tests: build tests/fixtures/jds/ with at least 20 realistic sample JDs and expected extracted skills;
write a test that reports extraction precision/recall over that set. Test edge cases (empty JD, huge JD, non-English).
Document the scoring formula in docs/DECISIONS.md.
```

## Phase 3 — Ingestion Workers (week 3–4.5)

```
Implement Phase 3: scheduled listing ingestion with Celery. Plan first, wait for approval.

- Celery app + Celery Beat configured in app/workers. Run the Celery worker and beat locally via `make worker` and `make beat` (not in docker-compose).
- Source adapters behind a common interface `ListingSource.fetch() -> list[RawListing]`.
  Implement ONLY: Greenhouse public board API, Lever public postings API, and one public jobs API (e.g. RemoteOK or Adzuna).
  NO scraping of sites that forbid it (see AGENTS.md).
- Normalisation: map raw listings to a Listing model (title, company, location, remote flag, salary min/max/currency
  if present, description, source, external_id, posted_at, content hash).
- Dedup: unique (source, external_id) plus content-hash check across sources.
- Reliability: retries with exponential backoff, per-source rate limiting, task idempotency, failure logged with context,
  an IngestionRun table (started, finished, fetched, inserted, skipped, errors).
- After insert, a follow-up task extracts skills (reuse the match extractor) into ListingSkill rows.
- Endpoints: GET /listings (filters + pagination), GET /listings/{id}, POST /listings/import (CSV/JSON),
  GET /ingestion/runs.
- Auto-match: nightly task scores new listings against the user's profile and exposes GET /listings?min_score=70.

Tests: mock all HTTP with respx/httpx mock; test dedup, retry behaviour, idempotency, and adapter parsing with saved fixtures.
```

## Phase 4 — Analytics + Platform Hardening (week 4.5–5.5)

```
Implement Phase 4: analytics and production hardening. Plan first, wait for approval.

Analytics endpoints (computed in SQL, not in Python loops):
- GET /analytics/skills/top?role=&location=&period=   top skills by frequency
- GET /analytics/skills/cooccurrence?skill=            skills that appear with a given skill
- GET /analytics/salary?role=&location=                min/median/p75 where salary data exists
- GET /analytics/trends?granularity=week               posting volume over time
- GET /analytics/my-gap                                skills in demand that the user's profile lacks
Use materialized views or summary tables refreshed by a Celery task; add Redis caching with sensible TTL and invalidation.
Show EXPLAIN ANALYZE before/after for at least one query and record real numbers in docs/DECISIONS.md.

Hardening:
- Per-user rate limiting (Redis), API keys as an alternative auth method, audit log table.
- Log request duration (duration_ms) and Celery task outcomes in the structured logs. No Prometheus.
- Global exception handling with the standard error format; request validation errors cleaned up.
- A simple benchmark script (plain Python + httpx, or pytest-benchmark) timing key endpoints, with results written to docs/PERFORMANCE.md (real measured numbers only).

Tests for each endpoint + cache behaviour. Coverage must stay ≥ 80%.
```

## Phase 5 — Polish + Demo (week 5–5.5)

```
Prepare CareerOps for portfolio showcase. Plan first, wait for approval. Do NOT add deployment, CI/CD or Docker for the app.

- Seed script (`make seed`) with realistic demo data and a demo user so a reviewer can try everything locally in minutes.
- README: one-paragraph pitch, architecture diagram (Mermaid), feature list, quick start (`make services`, `make migrate`, `make seed`, `make run`),
  example curl requests with real responses, tech stack, testing and coverage, design decisions summary, roadmap.
- Add docs/DEMO_SCRIPT.md: a 3-minute walkthrough script for a screen-recorded demo video.
- Add LICENSE and a clean-commit-history check.
- Security pass: pip-audit, no secrets in git history, CORS configured, input validation review.
Do not invent any numbers for the README; use only values measured in this repo.
```

---

## Utility prompts (use any time)

**Review before you commit**
```
Review the uncommitted changes like a strict senior engineer. List bugs, security issues, missing tests,
layering violations versus AGENTS.md, and naming problems. Do not change code yet; give a prioritised list.
```

**When tests fail**
```
Run `make test`. For each failure, explain the root cause first, then propose the minimal fix. Don't weaken
or delete tests to make them pass unless the test itself is wrong, and say so explicitly if so.
```

**Interview prep**
```
Based on this repo, write 15 likely backend interview questions an interviewer would ask about its design
(transactions, async, Celery reliability, indexing, auth, caching), each with a concise answer that
points to the exact file and function where I implemented it.
```
