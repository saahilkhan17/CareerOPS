# CareerOps

## What This Is

CareerOps is a job-search intelligence platform exposed as a Python backend API.
It tracks job applications with full status history, scores job descriptions
against the user's profile with a transparent deterministic match score, ingests
listings daily from legitimate public sources, and serves SQL-driven market
analytics. Built to be used daily by its author and to serve as the flagship
backend portfolio project for Python/FastAPI roles.

## Core Value

Reliable application tracking plus a trustworthy, explainable JD match score —
everything else supports these two.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Bootstrap: runnable local stack, health checks, config, logging, migrations (PLT-1..3, PLT-7)
- [ ] Auth: register/login/refresh/logout, hashed passwords + tokens, per-user isolation, API keys (AUTH-1..5)
- [ ] Tracker: application CRUD, status state machine + history, notes, reminders, filtered list, CSV export (TRK-1..7)
- [ ] Match: profile, skill taxonomy, JD extraction, deterministic scoring API + persisted results (MAT-1..8)
- [ ] Ingestion: Celery pipeline, legit-source adapters, normalization, dedup, retries, listing endpoints, auto-match (ING-1..8)
- [ ] Analytics + hardening: skills/salary/trends/my-gap endpoints, precomputed aggregates + cache, rate limits, audit log, benchmarks (ANA-1..6, PLT-4..6)
- [ ] Polish + demo: seed data, README, demo script, security pass (Phase 5)

### Out of Scope

- App Dockerfile, CI/CD, cloud deploy, K8s, Prometheus/Grafana, load-test infra — separate DevOps project
- Auto-applying to jobs — not in v1 (PRD non-goal)
- Scraping LinkedIn/Naukri/Indeed or any ToS-forbidding site — legal boundary
- Polished frontend dashboard — later phase
- Multi-org/team features and billing — not in v1
- Resume file generation/editing — v1 only suggests edits

## Context

- Greenfield repo (2026-10-12): no `app/`, `tests/`, `alembic/`, compose, Makefile yet.
- Planned from PRD.md v1.0 + AGENTS.md + OPENCODE_PROMPTS.md via `/gsd-ingest-docs`
  (MODE=new, 0 blockers). Intel in `.planning/intel/`.
- Personas: active job seeker (primary), portfolio reviewer (secondary), API integrator (tertiary).
- Deferred decisions (PRD §15): third jobs-API source, LLM provider/cost cap for MAT-7,
  dashboard stack, demo-user count.

## Constraints

- **Tech stack**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic,
  PG16 (+pgvector later), Redis, Celery+Beat, JWT, Pytest/httpx, Ruff, mypy — do not swap without asking
- **Architecture**: routers → services → repositories → models; schemas ≠ ORM models; async API layer
- **Scope**: one phase at a time; ideas → `docs/BACKLOG.md`; decisions → `docs/DECISIONS.md`
- **Quality**: ≥80% coverage, `make lint test` green, type hints everywhere, conventional commits
- **Honesty**: README numbers must be measured (benchmarks, EXPLAIN ANALYZE, extraction P/R)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Deterministic match score, LLM explanation optional and score-independent | Opaque scorers are untrustworthy; tests must be deterministic (PRD MAT-4/MAT-7) | — Pending |
| Ingestion from legitimate sources only (Greenhouse/Lever/public API/CSV) | ToS compliance; adapter interface + fixtures isolate source churn | — Pending |
| Compose runs only Postgres + Redis locally | Dev convenience; app deploy is a separate project | — Pending |
| GSD folder-local install (`.opencode/`), global install removed | User asked folder-only | ✓ Good |
| Ingest subagents unavailable → inline classification/synthesis | Pinned model missing in runtime; same schemas used, deviation logged | ⚠️ Revisit |

---
*Last updated: 2026-10-12 after ingest-docs bootstrap*
