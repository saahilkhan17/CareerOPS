# CareerOps: Product Requirements Document

**Version 1.0 · Status: Draft for build**

> **For the AI coding agent:** This file is the source of truth for what to build. Read it together with `AGENTS.md` before starting any phase. Requirement IDs (AUTH-1, TRK-2, MAT-4, ING-5, ANA-6, PLT-3, etc.) are referenced in prompts. Build only the phase you are asked to build. Plan first, then code, then test.

## 1. Overview

CareerOps is a job-search intelligence platform exposed as a Python backend API. It combines four capabilities: an application tracker, a job-description (JD) match scorer, a scheduled job-listing ingestion pipeline, and a job-market analytics layer. It is built to be used daily by its author and to serve as the flagship backend portfolio project for Python backend, FastAPI, API developer, and AI backend roles.

**One-line pitch:** Track every application, score every job description against your profile, and see which skills the market actually wants.

## 2. Problem Statement

- No single history of where each application stands, what changed, and when to follow up.
- Reading each JD manually to decide whether it fits is slow and inconsistent.
- Generic ATS checkers give opaque scores with no breakdown of what to fix.
- Market trends (in-demand skills, salary ranges) are anecdotal rather than measured.

## 3. Goals and Non-Goals

### Goals

1. Provide a reliable, secure API to manage applications with a full status history.
2. Provide a transparent, deterministic JD match score with a per-component breakdown.
3. Ingest listings daily from legitimate public sources with deduplication and retries.
4. Provide SQL-driven analytics on skills demand, salaries, and posting trends.
5. Demonstrate production-grade backend practices: layered architecture, migrations, background workers, caching, rate limiting, testing, and structured logging.

### Non-Goals (v1)

- Auto-applying to jobs or submitting forms on a user's behalf.
- Scraping sites whose terms of service forbid it (for example LinkedIn, Naukri, Indeed).
- A polished frontend (a dashboard is a later phase).
- Multi-organization or team features and billing.
- Resume file generation or editing (v1 only suggests edits).
- DevOps scope: application Dockerfile, CI/CD pipelines, cloud deployment, Kubernetes, Prometheus/Grafana, load-testing infrastructure (handled in a separate DevOps project).

## 4. Target Users

| Persona | Description | Key needs |
|---|---|---|
| Primary: Active job seeker (fresher or early career) | Applies to many roles across several tracks | Track applications, prioritize by fit, know what to improve |
| Secondary: Portfolio reviewer (recruiter or hiring manager) | Skims the repo and demo for evidence of engineering quality | Clear README, live demo, tests, architecture clarity |
| Tertiary: Developer integrating via API | Consumes the API from a script or future frontend | Stable endpoints, OpenAPI docs, API keys |

## 5. Scope by Phase

| Phase | Name | Outcome |
|---|---|---|
| 0 | Bootstrap | Repo, config, local dev services, health checks |
| 1 | Auth and Tracker | Users, applications, status machine, history, notes, reminders |
| 2 | JD Match Scoring | Profile, skill taxonomy, extraction, deterministic scoring API |
| 3 | Ingestion Workers | Celery pipeline, source adapters, dedup, auto-match |
| 4 | Analytics and Hardening | Analytics endpoints, caching, rate limits, query benchmarks |
| 5 | Polish and Demo | README, seed data, demo video, security pass |
| Later | Dashboard | Frontend and deeper analytics |

## 6. Functional Requirements

Priority key: **P0** = required for v1, **P1** = should have, **P2** = nice to have.

### 6.1 Authentication and Accounts (Phase 1)

| ID | Requirement | Priority |
|---|---|---|
| AUTH-1 | Users can register with email and password; passwords are hashed with argon2 or bcrypt | P0 |
| AUTH-2 | Users can log in and receive a short-lived access token (15 minutes) and a rotating refresh token | P0 |
| AUTH-3 | Refresh tokens are stored hashed, revocable, and invalidated on logout | P0 |
| AUTH-4 | All data is scoped to the authenticated user; cross-user access returns 404 or 403 | P0 |
| AUTH-5 | Users can create and revoke API keys as an alternative to JWT | P1 |

### 6.2 Application Tracker (Phase 1)

| ID | Requirement | Priority |
|---|---|---|
| TRK-1 | Create, read, update, delete job applications (company, title, URL, source, location, notes, resume version, applied date) | P0 |
| TRK-2 | Status state machine: saved, applied, oa, interview, offer, rejected, withdrawn; illegal transitions return 409 | P0 |
| TRK-3 | Every status change writes a StatusHistory row in the same transaction | P0 |
| TRK-4 | Users can add notes and set follow-up reminders on an application | P0 |
| TRK-5 | List endpoint supports filters (status, company, date range, text search), sorting, and limit/offset pagination with total count | P0 |
| TRK-6 | Export applications as CSV | P1 |
| TRK-7 | Reminder-due query endpoint (optional notification hook later) | P2 |

### 6.3 JD Match Scoring (Phase 2)

| ID | Requirement | Priority |
|---|---|---|
| MAT-1 | Users maintain a profile: skills (with level or years), target roles, education, preferences | P0 |
| MAT-2 | A versioned skill taxonomy maps aliases to canonical skills (for example "postgres" to PostgreSQL) and is easy to extend | P0 |
| MAT-3 | Extraction service pulls skills, required versus preferred split, minimum years of experience, and seniority signals from raw JD text | P0 |
| MAT-4 | Scoring is deterministic and does not use an LLM: weighted 0 to 100 score from required-skill coverage, preferred-skill coverage, experience fit, and title similarity; weights are configurable | P0 |
| MAT-5 | Response includes score, per-component breakdown, matched skills, and missing skills | P0 |
| MAT-6 | Endpoints: POST /match for pasted JD text and POST /match/{application_id}; results persisted in MatchResult | P0 |
| MAT-7 | Optional LLM explanation (behind a feature flag and an interface) turns the breakdown into resume-improvement suggestions; the numeric score never depends on it | P1 |
| MAT-8 | Embedding-based similarity using pgvector as an additional scoring signal | P2 |

### 6.4 Listing Ingestion (Phase 3)

| ID | Requirement | Priority |
|---|---|---|
| ING-1 | Source adapters implement a common interface and use only legitimate sources: Greenhouse and Lever public board endpoints, one public jobs API, and CSV/JSON import | P0 |
| ING-2 | Celery Beat schedules ingestion runs; each run is recorded in IngestionRun (fetched, inserted, skipped, errors) | P0 |
| ING-3 | Listings are normalized (title, company, location, remote flag, salary range if present, description, source, external ID, posted date, content hash) | P0 |
| ING-4 | Deduplication by unique (source, external_id) and by cross-source content hash | P0 |
| ING-5 | Tasks are idempotent and use retries with exponential backoff and per-source rate limiting | P0 |
| ING-6 | After insert, skills are extracted into ListingSkill rows | P0 |
| ING-7 | Endpoints: GET /listings (filters and pagination), GET /listings/{id}, POST /listings/import, GET /ingestion/runs | P0 |
| ING-8 | Nightly auto-match scores new listings against the user's profile; GET /listings?min_score=N | P1 |

### 6.5 Analytics (Phase 4)

| ID | Requirement | Priority |
|---|---|---|
| ANA-1 | GET /analytics/skills/top by role, location, and period | P0 |
| ANA-2 | GET /analytics/skills/cooccurrence for a given skill | P1 |
| ANA-3 | GET /analytics/salary (min, median, p75) where salary data exists | P1 |
| ANA-4 | GET /analytics/trends with weekly posting volume | P0 |
| ANA-5 | GET /analytics/my-gap lists in-demand skills missing from the user's profile | P0 |
| ANA-6 | Heavy aggregates use materialized views or summary tables refreshed by a Celery task, with Redis caching and defined TTL and invalidation | P0 |

### 6.6 Platform (Phases 0 and 4)

| ID | Requirement | Priority |
|---|---|---|
| PLT-1 | /health and /ready endpoints | P0 |
| PLT-2 | Structured JSON logging with a request ID on every log line | P0 |
| PLT-3 | Consistent error format: `{"error": {"code": "...", "message": "..."}}` | P0 |
| PLT-4 | Per-user rate limiting backed by Redis | P1 |
| PLT-5 | Request duration (duration_ms) and Celery task outcomes recorded in structured logs | P1 |
| PLT-6 | Audit log of security-relevant and state-changing actions | P1 |
| PLT-7 | OpenAPI documentation with example requests and responses | P0 |

## 7. Data Model (Logical)

| Entity | Key fields | Notes |
|---|---|---|
| User | id, email, password_hash, created_at | Owner of all personal data |
| RefreshToken | id, user_id, token_hash, expires_at, revoked_at | Rotating, revocable |
| ApiKey | id, user_id, key_hash, name, last_used_at | Optional auth |
| Profile | user_id, skills (with level), target_roles, education, preferences | One per user |
| Company | id, name, website | Shared lookup, deduplicated by name |
| JobApplication | id, user_id, company_id, title, url, status, resume_version, applied_at | Indexed on (user_id, status) and (user_id, created_at) |
| StatusHistory | id, application_id, from_status, to_status, changed_at | Append-only |
| Note / Reminder | id, application_id, body or due_at | Child of application |
| Listing | id, source, external_id, title, company, location, remote, salary_min, salary_max, currency, description, content_hash, posted_at | Unique (source, external_id) |
| ListingSkill | listing_id, skill_id, required | Feeds analytics |
| Skill | id, canonical_name, aliases, taxonomy_version | From taxonomy |
| MatchResult | id, user_id, listing_id or application_id, score, breakdown (JSON), created_at | Persisted for history |
| IngestionRun | id, source, started_at, finished_at, fetched, inserted, skipped, errors | Operational record |
| AuditLog | id, user_id, action, entity, created_at | Append-only |

## 8. API Surface (Summary)

| Area | Endpoints |
|---|---|
| Auth | POST /auth/register, /auth/login, /auth/refresh, /auth/logout; POST and DELETE /auth/api-keys |
| Profile | GET and PUT /profile |
| Tracker | CRUD /applications; POST /applications/{id}/status; POST /applications/{id}/notes; POST /applications/{id}/reminders; GET /applications/export.csv |
| Match | POST /match; POST /match/{application_id}; GET /match/history |
| Listings | GET /listings; GET /listings/{id}; POST /listings/import; GET /ingestion/runs |
| Analytics | GET /analytics/skills/top, /skills/cooccurrence, /salary, /trends, /my-gap |
| Ops | GET /health, /ready |

## 9. Technical Architecture

Clients (Swagger UI, scripts, later a dashboard) call a FastAPI service organised as routers, services, repositories, and models. The service uses PostgreSQL (with pgvector in a later increment) for persistence and Redis for caching, rate limiting, and the Celery broker. Celery workers and Celery Beat run ingestion, skill extraction, auto-matching, and analytics refresh tasks.

```
Client / Swagger / (later) dashboard
        |
   FastAPI  (routers -> services -> repositories -> models)
        |
  +-----+--------------+----------------+
  PostgreSQL        Redis            Celery workers + Beat
  (+pgvector)   (cache, limits,      - ingest listings
                 broker)             - extract skills
                                     - auto-match
                                     - refresh analytics
```

| Layer | Choice |
|---|---|
| Language and framework | Python 3.12, FastAPI, Pydantic v2 |
| Data access | SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 (+ pgvector later) |
| Cache and queue | Redis, Celery, Celery Beat |
| Auth | JWT access and refresh tokens, optional API keys |
| Quality | Pytest, pytest-asyncio, httpx, respx, Ruff, mypy |
| Local dev | Docker Compose for Postgres and Redis only; Makefile for common commands |
| Observability | Structured JSON logs with request IDs and timings |

Design principles: routers never access the database directly; schemas are separate from ORM models; all configuration comes from environment variables; every schema change has an Alembic migration; the match score is deterministic and testable.

## 10. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Security | Hashed passwords and tokens, no secrets in git, per-user data isolation, CORS and security headers configured, dependency audit with pip-audit |
| Reliability | Idempotent, retried background tasks; failed ingestion is logged with context and never corrupts data |
| Performance (targets) | Common read endpoints under 200 ms p95 at moderate load; analytics endpoints served from cached or precomputed aggregates; actual numbers must be measured with a simple benchmark script and recorded in docs/PERFORMANCE.md |
| Quality | At least 80% test coverage; `make lint test` passes locally before every commit |
| Maintainability | Type hints throughout, small functions, design decisions recorded in docs/DECISIONS.md |
| Compliance | Use only sources whose terms permit programmatic access; respect robots.txt and rate limits |
| Portability | Local start with `make services` then `make run` |

## 11. Success Metrics

These are targets to be verified by measurement, not claims.

| Metric | Target |
|---|---|
| Test coverage | 80% or higher |
| JD skill extraction quality | Precision and recall reported over a labeled set of at least 20 JDs (stretch: 50) |
| Ingestion | Scheduled daily run completes with a recorded IngestionRun and zero duplicate listings |
| Analytics latency | Measured improvement from caching or materialized views, documented with EXPLAIN ANALYZE |
| Personal usage | The author tracks real applications in their own local instance |
| Portfolio outcome | README with architecture diagram and screenshots, seeded demo data, and a demo video |

## 12. Acceptance Criteria (Per Phase)

- **Phase 0:** `make services` and `make run` start the app; `/health` and `/ready` respond; `make lint test` passes.
- **Phase 1:** All TRK and AUTH P0 requirements work; cross-user access tests pass; migrations applied.
- **Phase 2:** /match returns score and breakdown; extraction metrics reported on the labeled JD set; scoring formula documented.
- **Phase 3:** Scheduled ingestion populates listings without duplicates; retries and idempotency tested with mocked HTTP.
- **Phase 4:** Analytics endpoints return correct results; cache behavior tested; query timings recorded.
- **Phase 5:** Seeded local demo works end to end; README, demo video, and security pass complete.

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Source terms of service or API changes break ingestion | Missing data | Adapter interface, saved fixtures in tests, CSV/JSON import fallback |
| Skill extraction is noisy | Poor match scores | Curated taxonomy, labeled test set, tunable weights |
| Scope creep delays completion | Unfinished flagship | Strict phase boundaries, docs/BACKLOG.md for new ideas |
| LLM output is inconsistent | Untrustworthy results | Keep LLM optional and separate from the numeric score |
| Salary data is sparse | Weak salary analytics | Report sample sizes and show results only above a minimum count |
| AI coding agent drifts from design | Messy codebase | AGENTS.md rules, plan-first workflow, review every diff |

## 14. Timeline (Estimate)

| Phase | Duration |
|---|---|
| 0: Bootstrap | 1 to 2 days |
| 1: Auth and Tracker | 1.5 weeks |
| 2: JD Match Scoring | 1.5 weeks |
| 3: Ingestion Workers | 1.5 weeks |
| 4: Analytics and Hardening | 1 week |
| 5: Polish and Demo | 0.5 week |

Total: roughly five to six weeks of focused work.

## 15. Open Questions

1. Which public jobs API will be the third source (RemoteOK, Adzuna, or another)?
2. Should the LLM explanation use Claude or another provider, and what monthly cost cap applies?
3. Will the frontend dashboard be React or Streamlit?
4. Is a single seeded demo user enough, or should the demo support multiple isolated users?
