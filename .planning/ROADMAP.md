# Roadmap: CareerOps

## Overview

Greenfield backend build in PRD phase order: bootstrap the runnable skeleton,
then Auth+Tracker, Match scoring, Ingestion workers, Analytics+hardening, and a
portfolio polish pass. Each phase ends at its PRD §12 acceptance criteria plus
the per-phase definition of done (code + tests + migration + README + DECISIONS + commits).

## Phases

- [ ] **Phase 1: Bootstrap (PRD Phase 0)** - Runnable skeleton, config, health checks
- [ ] **Phase 2: Auth + Tracker (PRD Phase 1)** - Users, applications, state machine, history
- [ ] **Phase 3: JD Match Scoring (PRD Phase 2)** - Profile, taxonomy, extraction, deterministic scoring
- [ ] **Phase 4: Ingestion Workers (PRD Phase 3)** - Celery pipeline, adapters, dedup, auto-match
- [ ] **Phase 5: Analytics + Hardening (PRD Phase 4)** - Analytics endpoints, cache, rate limits, benchmarks
- [ ] **Phase 6: Polish + Demo (PRD Phase 5)** - Seed data, README, demo script, security pass

## Phase Details

### Phase 1: Bootstrap (PRD Phase 0)
**Goal**: `make services` + `make run` start the app; /health and /ready respond; `make lint test` passes.
**Depends on**: Nothing (first phase)
**Requirements**: PLT-1, PLT-2, PLT-3, PLT-7
**Success Criteria** (what must be TRUE):
  1. Reviewer runs three commands and gets a responding API with OpenAPI docs
  2. Request-ID JSON logging visible on every request
  3. Async SQLAlchemy + Alembic initialized; config from env with .env.example
  4. Health-check test passes; lint clean
**Plans**: 1 plan

Plans:
- [x] 01-01: Bootstrap skeleton (built 2026-10-12: 6 tests, 88.7% cov, lint+mypy clean)

### Phase 2: Auth + Tracker (PRD Phase 1)
**Goal**: Users manage applications end to end with a guarded status history no other user can see.
**Depends on**: Phase 1
**Requirements**: AUTH-1, AUTH-2, AUTH-3, AUTH-4, AUTH-5, TRK-1, TRK-2, TRK-3, TRK-4, TRK-5, TRK-6, TRK-7
**Success Criteria** (what must be TRUE):
  1. User can register, log in, refresh, log out; cross-user access returns 404/403
  2. User can CRUD applications and move them through the state machine; illegal moves get 409
  3. Every status change has a StatusHistory row written in the same transaction
  4. Filtered/sorted/paginated list, CSV export, reminders all work with tests
**Plans**: 2 plans

Plans:
- [x] 02-01: Auth module (built 2026-10-12: register/login/refresh/logout/me/API keys)
- [x] 02-02: Tracker module (built 2026-10-12: CRUD, machine, history, notes, reminders, CSV, 0002 migration)

### Phase 3: JD Match Scoring (PRD Phase 2)
**Goal**: Pasted or linked JDs return a deterministic score with a breakdown a user can act on.
**Depends on**: Phase 2
**Requirements**: MAT-1, MAT-2, MAT-3, MAT-4, MAT-5, MAT-6, MAT-7, MAT-8
**Success Criteria** (what must be TRUE):
  1. POST /match returns score 0–100 plus per-component breakdown, matched and missing skills
  2. Same result for same inputs across runs (LLM never touches the number)
  3. Extraction precision/recall reported over ≥20 labeled JDs; formula in docs/DECISIONS.md
  4. Edge cases handled: empty, huge, non-English JDs
**Plans**: TBD

Plans:
- [ ] 03-01: TBD at plan time

### Phase 4: Ingestion Workers (PRD Phase 3)
**Goal**: Scheduled ingestion fills listings without duplicates and auto-scores them against the profile.
**Depends on**: Phase 3 (reuses match extractor for ListingSkill rows)
**Requirements**: ING-1, ING-2, ING-3, ING-4, ING-5, ING-6, ING-7, ING-8
**Success Criteria** (what must be TRUE):
  1. Beat-scheduled run completes with an IngestionRun record; zero duplicate listings
  2. Retries/backoff, per-source rate limits, and idempotency proven with mocked HTTP
  3. Listing endpoints + CSV/JSON import + min_score filter all work
**Plans**: TBD

Plans:
- [ ] 04-01: TBD at plan time

### Phase 5: Analytics + Hardening (PRD Phase 4)
**Goal**: Analytics endpoints serve correct results fast, and the platform is rate-limited, audited, and benchmarked.
**Depends on**: Phase 4
**Requirements**: ANA-1, ANA-2, ANA-3, ANA-4, ANA-5, ANA-6, PLT-4, PLT-5, PLT-6
**Success Criteria** (what must be TRUE):
  1. All five analytics endpoints return correct SQL-computed results with tests
  2. Cache behavior tested; EXPLAIN ANALYZE before/after recorded with real numbers
  3. Rate limiting, API keys, audit log, and benchmark script (docs/PERFORMANCE.md) done; coverage ≥80%
**Plans**: TBD

Plans:
- [ ] 05-01: TBD at plan time

### Phase 6: Polish + Demo (PRD Phase 5)
**Goal**: A reviewer can try everything locally in minutes and see a portfolio-ready README.
**Depends on**: Phase 5
**Requirements**: Polish/demo acceptance (PRD §12 Phase 5)
**Success Criteria** (what must be TRUE):
  1. `make seed` gives a demo user with realistic data covering all features
  2. README has pitch, architecture diagram, quickstart, real curl examples, measured stats only
  3. Demo script, LICENSE, pip-audit + secrets + CORS + validation review complete
**Plans**: TBD

Plans:
- [ ] 06-01: TBD at plan time

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Bootstrap | 1/1 | Complete | 2026-10-12 |
| 2. Auth + Tracker | 2/2 | Complete | 2026-10-12 |
| 3. JD Match Scoring | 0/TBD | Not started | - |
| 4. Ingestion Workers | 0/TBD | Not started | - |
| 5. Analytics + Hardening | 0/TBD | Not started | - |
| 6. Polish + Demo | 0/TBD | Not started | - |
