# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-12)

**Core value:** Reliable application tracking plus a trustworthy, explainable JD match score.
**Current focus:** Phase 5: Analytics + Hardening (ready to plan)

## Current Position

Phase: 5 of 6 (Analytics + Hardening)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-10-12 — Phase 4 built+verified (142 tests, 98% cov, respx suite)

Progress: [███████░░░] 67%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: -
- Total execution time: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Ingest]: Folder-local GSD install; global install removed
- [Ingest]: Inline classification/synthesis (subagent model unavailable)
- [Phase 1]: Stdlib JSON logging; lint scoped to app/tests/alembic; setuptools
  packages.find restricted to app* (flat-layout discovery fix)
- [Phase 2]: bcrypt+JWT+opaque-refresh auth; strict state machine (13 edges);
  coverage greenlet concurrency; sqlite/StaticPool tests; naive-UTC clock
- [Phase 3]: 78-skill taxonomy + deterministic extractor (P/R 1.000/1.000);
  weighted scorer + breakdown; LLM behind flag+seam; MAT-8 deferred to v2
- [Phase 4]: Greenhouse/Lever/RemoteOK adapters (RemoteOK picked over Adzuna);
  hash+id dedup, retries+throttle, idempotent capped auto-match, 0004 migration

### Pending Todos

None yet.

### Blockers/Concerns

- Subagent runtimes pin `anthropic/claude-haiku-4-5`, unavailable here — plan/execute
  workflows that spawn subagents will need inline fallback or a model fix. (From: ingest)

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| PRD §15 | Third jobs-API source choice | Open | 2026-10-12 |
| PRD §15 | LLM provider + cost cap (MAT-7) | Open | 2026-10-12 |
| PRD §15 | Dashboard stack | Open | 2026-10-12 |
| PRD §15 | Demo-user count | Open | 2026-10-12 |

## Session Continuity

Last session: 2026-10-12
Stopped at: Phase 4 complete and committed; Phase 5 ready to plan
Resume file: None
