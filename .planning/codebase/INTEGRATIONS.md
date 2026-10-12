# INTEGRATIONS — CareerOps (2026-10-12)

No live integrations. All external touchpoints are planned, not implemented.

## Planned (per `docs/PRD.md`, `AGENTS.md`)
- PostgreSQL 16 (+pgvector later) via async SQLAlchemy + Alembic
- Redis — cache, rate limiting, Celery broker
- Celery workers + Celery Beat — ingestion, skill extraction, auto-match, analytics refresh
- Greenhouse public board API + Lever public postings API + one public jobs API (RemoteOK/Adzuna TBD)
- Optional LLM explanation service behind feature flag + interface (provider TBD per PRD open Q3)
- Prometheus `/metrics`, GitHub Actions (lint+mypy+tests+docker build), deploy target Render/Fly/Railway TBD
- Hard rule: NO scraping of LinkedIn/Naukri/Indeed; respect robots.txt + rate limits

## Current repo reality
- `deve/scripts/scope-check.py` — pure stdlib (argparse, re, sys, pathlib), no deps
- `deve/scripts/secret-scan.sh` — grep-based secret patterns (api_key, secret, password, token, ASIA, sk-, ghp_)
- `deve/scripts/spend-log.sh` — appends to `.harness/telemetry/spend.csv` (`.harness/` not present in repo)
- `verify.sh` references `.harness/` paths that do not exist here — will fail until adapted
- No network calls, no DB, no auth, no webhooks today

## Implications
- Phase 0: no external services needed beyond Docker Postgres/Redis.
- Phase 3 must add `respx`/httpx mocks + saved fixtures; never hit live boards in tests.
- Secret-scan patterns must be kept; never commit `.env` or tokens.
