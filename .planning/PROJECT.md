# CareerOps

## What This Is

CareerOps is a job-search intelligence platform exposed as a Python backend API. It combines an application tracker, a deterministic JD match scorer, a scheduled listing-ingestion pipeline, and a SQL-driven analytics layer. Built to be used daily by its author and to serve as the flagship backend portfolio project for Python backend / FastAPI / AI backend roles.

## Core Value

Track every application, score every job description against your profile, and see which skills the market actually wants.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Phase 0 Bootstrap: repo, Docker, CI, config, health checks (`make up`, `make lint test` green)
- [ ] Phase 1 Auth + Tracker: register/login/refresh/logout, JWT + revocable refresh, `get_current_user`; Company/JobApplication/StatusHistory/Note/Reminder; status state machine with 409 on illegal transitions + history row per transition; filtered/sorted/paginated list; CSV export
- [ ] Phase 2 JD Match Scoring: profile + versioned skill taxonomy; deterministic extraction + weighted 0–100 scoring with breakdown/matched/missing; `POST /match`, `POST /match/{application_id}`, persisted MatchResult; optional flagged LLM explanation (never affects score)
- [ ] Phase 3 Ingestion Workers: Celery + Beat; Greenhouse/Lever/public-API adapters behind `ListingSource.fetch()`; normalization + dedup + retries/backoff/rate-limit/idempotency; IngestionRun records; ListingSkill extraction; listings endpoints + auto-match
- [ ] Phase 4 Analytics + Hardening: skills/top, cooccurrence, salary, trends, my-gap (SQL, materialized views/summary tables, Redis cache); rate limits, API keys, audit log, Prometheus metrics, error format, load tests with measured numbers
- [ ] Phase 5 Deploy + Polish: prod Docker + hosting, CI deploy, seed/demo data, README/DEPLOY/PERFORMANCE docs, security pass (no invented numbers)

### Out of Scope

- Auto-applying to jobs or submitting forms — v1 is read/track/score only
- Scraping sites whose ToS forbid it (LinkedIn, Naukri, Indeed) — legitimate sources + CSV import only
- Polished frontend dashboard — later phase
- Multi-org/team features and billing — single-user scope v1
- Resume file generation/editing — v1 suggests edits only

## Context

- Source of truth: `docs/PRD.md` (v1.0 draft, requirement IDs AUTH/TRK/MAT/ING/ANA/PLT) + `AGENTS.md` (stack, layers, commands, don'ts, DoD) + `OPENCODE_PROMPTS.md` (phased prompts).
- Repo today: docs + `deve/` Solo harness + `.opencode/` GSD v1.42.3. No `app/`, `tests/`, Docker, Makefile yet. See `.planning/codebase/`.
- PRD open questions (unresolved): third jobs-API choice, hosting provider, LLM provider/cost cap, dashboard stack, demo single- vs multi-user.

## Constraints

- **Tech stack**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16 (+pgvector later), Redis, Celery + Beat, JWT access (15min) + rotating refresh, Pytest/pytest-asyncio/httpx, Ruff + mypy, Docker + Compose, GitHub Actions, uv or pip-tools — do not swap without asking
- **Architecture**: `routers → services → repositories → models`; schemas separate from ORM; env-only config; Alembic per schema change; standard error format; request-ID JSON logging; `/health` + `/ready`
- **Quality**: plan-first, one feature per step, tests with every feature, ≥80% coverage, `make lint test` green, conventional commits, decisions in `docs/DECISIONS.md`
- **Compliance**: legitimate sources only; robots.txt + rate limits; no plaintext passwords; no token/PII logging; no invented README metrics

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GSD local install (`--opencode --local`) | Folder-only, per user request | ✓ Good |
| Codebase map before init | User chose mapping; confirmed greenfield-under-docs | ✓ Good |
| `make` canonical over `task` | AGENTS.md mandates Makefile; Taskfile stays optional | — Pending |
| Pin Python 3.12 in Docker/CI | Local is 3.14; avoid async/SQLAlchemy drift | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-12 after initialization*
