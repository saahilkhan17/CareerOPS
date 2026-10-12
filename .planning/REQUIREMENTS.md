# Requirements: CareerOps

**Defined:** 2026-10-12
**Core Value:** Reliable application tracking plus a trustworthy, explainable JD match score.

## v1 Requirements

IDs are the PRD requirement IDs (source of truth: PRD.md §6).

### Platform / Bootstrap

- [ ] **PLT-1**: /health and /ready endpoints respond
- [ ] **PLT-2**: Structured JSON logging with request ID on every line
- [ ] **PLT-3**: Consistent error format `{"error": {"code": ..., "message": ...}}`
- [ ] **PLT-7**: OpenAPI docs with example requests/responses

### Authentication

- [ ] **AUTH-1**: Register with email+password; argon2/bcrypt hashing
- [ ] **AUTH-2**: Login returns 15-min access JWT + rotating refresh token
- [ ] **AUTH-3**: Refresh tokens stored hashed, revocable, invalidated on logout
- [ ] **AUTH-4**: All data scoped to user; cross-user access → 404/403
- [ ] **AUTH-5**: API keys creatable/revocable as JWT alternative

### Tracker

- [ ] **TRK-1**: Application CRUD (company, title, URL, source, location, notes, resume version, applied date)
- [ ] **TRK-2**: Status state machine (saved, applied, oa, interview, offer, rejected, withdrawn); illegal → 409
- [ ] **TRK-3**: Every status change writes StatusHistory row in same transaction
- [ ] **TRK-4**: Notes + follow-up reminders per application
- [ ] **TRK-5**: List with filters/sorting/limit-offset pagination + total
- [ ] **TRK-6**: CSV export
- [ ] **TRK-7**: Reminder-due query endpoint

### Match

- [ ] **MAT-1**: Profile (skills w/ level-years, target roles, education, preferences)
- [ ] **MAT-2**: Versioned skill taxonomy (aliases → canonical), extendable
- [ ] **MAT-3**: Extraction (skills, required-vs-preferred, min YoE, seniority signals)
- [ ] **MAT-4**: Deterministic 0–100 weighted score, configurable weights, no LLM
- [ ] **MAT-5**: Response has score + breakdown + matched/missing skills
- [ ] **MAT-6**: POST /match + POST /match/{application_id}; MatchResult persisted
- [ ] **MAT-7**: Optional LLM explanation behind flag+interface; never affects score
- [ ] **MAT-8**: pgvector embedding similarity as extra signal

### Ingestion

- [ ] **ING-1**: Adapters behind `ListingSource.fetch()`; legitimate sources only
- [ ] **ING-2**: Beat-scheduled runs recorded in IngestionRun
- [ ] **ING-3**: Normalized Listing fields incl. content hash
- [ ] **ING-4**: Dedup by (source, external_id) + cross-source content hash
- [ ] **ING-5**: Idempotent tasks, exponential-backoff retries, per-source rate limits
- [ ] **ING-6**: Post-insert skill extraction into ListingSkill rows
- [ ] **ING-7**: Listing/ingestion endpoints (GET /listings, GET /listings/{id}, POST /listings/import, GET /ingestion/runs)
- [ ] **ING-8**: Nightly auto-match; GET /listings?min_score=N

### Analytics + Hardening

- [ ] **ANA-1**: GET /analytics/skills/top (role, location, period)
- [ ] **ANA-2**: GET /analytics/skills/cooccurrence
- [ ] **ANA-3**: GET /analytics/salary (min/median/p75, min sample count)
- [ ] **ANA-4**: GET /analytics/trends (weekly volume)
- [ ] **ANA-5**: GET /analytics/my-gap
- [ ] **ANA-6**: Precomputed aggregates + Celery refresh + Redis cache w/ TTL
- [ ] **PLT-4**: Per-user Redis rate limiting
- [ ] **PLT-5**: duration_ms + Celery outcomes in structured logs
- [ ] **PLT-6**: Audit log of security/state-changing actions

## v2 Requirements

Deferred/future (tracked, not in roadmap):

- **Dashboard**: Frontend + deeper analytics (PRD "Later" phase)
- **MAT-8** may slip to v2 if pgvector work overruns (currently P2 in v1)

## Out of Scope

| Feature | Reason |
|---------|--------|
| App Dockerfile / CI/CD / cloud / K8s / monitoring stack | Separate DevOps project (AGENTS.md) |
| Auto-apply | PRD non-goal |
| Forbidden-site scraping | ToS boundary (hard don't) |
| Multi-org / billing | PRD non-goal |
| Resume file generation | v1 suggests edits only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLT-1, PLT-2, PLT-3, PLT-7 | Phase 1 | Pending |
| AUTH-1..5, TRK-1..7 | Phase 2 | Pending |
| MAT-1..8 | Phase 3 | Pending |
| ING-1..8 | Phase 4 | Pending |
| ANA-1..6, PLT-4..6 | Phase 5 | Pending |
| Polish/demo acceptance | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 38 total
- Mapped to phases: 38
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-12*
*Last updated: 2026-10-12 after ingest-docs bootstrap*
