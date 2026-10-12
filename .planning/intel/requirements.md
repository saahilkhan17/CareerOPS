# Intel: Requirements (synthesized from PRD §6)

## Auth (Phase 1)
- AUTH-1 (P0): Register with email+password; argon2/bcrypt hashing.
- AUTH-2 (P0): Login returns 15-min access JWT + rotating refresh token.
- AUTH-3 (P0): Refresh tokens stored hashed, revocable, invalidated on logout.
- AUTH-4 (P0): All data scoped to authenticated user; cross-user access → 404/403.
- AUTH-5 (P1): API keys creatable/revocable as JWT alternative.

## Tracker (Phase 1)
- TRK-1 (P0): CRUD job applications (company, title, URL, source, location,
  notes, resume version, applied date).
- TRK-2 (P0): Status state machine saved→applied→oa→interview→offer |
  rejected | withdrawn; illegal transitions → 409.
- TRK-3 (P0): Every status change writes StatusHistory row in same transaction.
- TRK-4 (P0): Notes + follow-up reminders per application.
- TRK-5 (P0): List with filters (status, company, date range, text search),
  sorting, limit/offset pagination + total.
- TRK-6 (P1): CSV export.
- TRK-7 (P2): Reminder-due query endpoint.

## Match (Phase 2)
- MAT-1 (P0): Profile — skills (level/years), target roles, education, preferences.
- MAT-2 (P0): Versioned skill taxonomy (aliases → canonical), easily extendable.
- MAT-3 (P0): Extraction — skills, required-vs-preferred split, min YoE, seniority signals.
- MAT-4 (P0): Deterministic 0–100 weighted score (required coverage, preferred
  coverage, experience fit, title similarity); configurable weights; no LLM.
- MAT-5 (P0): Response has score, per-component breakdown, matched + missing skills.
- MAT-6 (P0): POST /match (pasted JD) + POST /match/{application_id}; persist MatchResult.
- MAT-7 (P1): Optional LLM explanation behind flag+interface; never affects score.
- MAT-8 (P2): pgvector embedding similarity as extra signal.

## Ingestion (Phase 3)
- ING-1 (P0): Adapters behind `ListingSource.fetch()`; legitimate sources only.
- ING-2 (P0): Celery Beat scheduled runs recorded in IngestionRun.
- ING-3 (P0): Normalized Listing (title, company, location, remote, salary, description,
  source, external_id, posted_at, content hash).
- ING-4 (P0): Dedup by (source, external_id) + cross-source content hash.
- ING-5 (P0): Idempotent tasks; retries with exponential backoff; per-source rate limits.
- ING-6 (P0): Post-insert skill extraction into ListingSkill rows.
- ING-7 (P0): GET /listings (+filters/pagination), GET /listings/{id},
  POST /listings/import, GET /ingestion/runs.
- ING-8 (P1): Nightly auto-match vs profile; GET /listings?min_score=N.

## Analytics (Phase 4)
- ANA-1 (P0): GET /analytics/skills/top (role, location, period).
- ANA-2 (P1): GET /analytics/skills/cooccurrence.
- ANA-3 (P1): GET /analytics/salary (min/median/p75, min sample count).
- ANA-4 (P0): GET /analytics/trends (weekly volume).
- ANA-5 (P0): GET /analytics/my-gap (in-demand skills missing from profile).
- ANA-6 (P0): Materialized views/summary tables + Celery refresh + Redis cache w/ TTL.

## Platform (Phases 0+4)
- PLT-1 (P0): /health + /ready.
- PLT-2 (P0): Structured JSON logging with request ID.
- PLT-3 (P0): Standard error format.
- PLT-4 (P1): Per-user Redis rate limiting.
- PLT-5 (P1): duration_ms + Celery outcomes in logs.
- PLT-6 (P1): Audit log of security/state-changing actions.
- PLT-7 (P0): OpenAPI docs with examples.
