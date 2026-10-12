# Demo Script (3 minutes, for a screen recording)

Setup (before recording): `make services && make migrate && make seed && make run`.
Seed login: demo@careerops.dev / demo1234. Open http://localhost:8000/docs.

## 0:00–0:20 — The problem (talking head or title card)

"Applying to dozens of roles across sheets, tabs, and memory. Reading every JD
by hand. Generic ATS checkers with mystery scores. CareerOps fixes all three:
track, score, and measure — one backend API."

## 0:20–1:00 — Track (Swagger: /applications)

1. `POST /applications` — Acme, Backend Engineer → 201, status `saved`.
2. `POST /applications/{id}/status` → `applied` → 200; then try
   `saved → offer` on a second app → **409** with the transition error.
3. `GET /applications/{id}/history` — every move recorded in the same
   transaction. `GET /applications/reminders/due` — the overdue follow-up
   from the seed data is already there.

Say: "Illegal transitions are rejected, history is atomic, and cross-user
access returns 404 — tested both directions."

## 1:00–1:50 — Score (Swagger: /match)

1. `GET /profile` — the demo profile: Python 4y, FastAPI 3y, PostgreSQL 4y.
2. `POST /match` with a Python/FastAPI JD → a score with a per-component
   breakdown: required coverage, preferred coverage, experience fit, title
   similarity, plus missing skills and suggestions.
3. Point at `llm_explanation: null` — "the number is deterministic; the
   optional LLM layer can only add words, never change the score."

## 1:50–2:40 — Market (Swagger: /listings, /analytics)

1. `GET /listings?min_score=70` — only listings auto-matched above 70.
2. `GET /analytics/skills/top` — Python leads the seeded market.
3. `GET /analytics/my-gap` — in-demand skills the demo profile lacks.
4. `GET /analytics/salary?min_n=1` — bands with sample counts, gated output.

Say: "Aggregates run in SQL over a precomputed summary table with Redis
caching — EXPLAIN and timings are in the repo."

## 2:40–3:00 — Engineering (terminal)

1. `make lint test` → green: 166 tests, ~98% coverage, ruff + strict mypy.
2. `git log --oneline` — one feature per commit, conventional messages.
3. Close: "Repo, seed data, and decisions log are all in the README. Thanks."
