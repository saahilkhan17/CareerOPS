# Intel: Context

- **Product**: CareerOps — job-search intelligence platform (Python backend API).
  Pitch: "Track every application, score every job description against your profile,
  and see which skills the market actually wants."
- **Personas**: Primary — active job seeker (fresher/early career). Secondary —
  portfolio reviewer (recruiter/hiring manager). Tertiary — API-integrating developer.
- **Repo state (2026-10-12)**: Greenfield. No `app/`, `tests/`, `alembic/`,
  `docker-compose.yml`, `Makefile`, `README.md`, `docs/` yet. Phase 0 not started.
  `.git/` exists at root. `deve/` harness is process tooling, excluded from product ingest.
- **Architecture sketch** (PRD §9): clients → FastAPI (routers→services→
  repositories→models) → PostgreSQL (+pgvector later) / Redis / Celery+Beat
  (ingest, skill extraction, auto-match, analytics refresh).
- **Data model** (PRD §7): User, RefreshToken, ApiKey, Profile, Company,
  JobApplication, StatusHistory, Note/Reminder, Listing, ListingSkill, Skill,
  MatchResult, IngestionRun, AuditLog.
- **Open questions** (PRD §15, unresolved — INFO only): third jobs-API source
  choice; LLM provider + cost cap for MAT-7; dashboard stack; single vs multi demo user.
- **Success metrics** (to be measured, not claimed): ≥80% coverage; extraction
  precision/recall over ≥20 labeled JDs; zero-duplicate daily ingestion;
  documented analytics latency improvement; author dogfoods local instance;
  README + seed demo + demo video.
