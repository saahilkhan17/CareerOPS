# Performance (measured, not estimated)

Measured: 2026-10-12 07:04 UTC · sqlite (in-process) · 50 applications · 300 listings

| Endpoint | Mean ms |
|---|---|
| GET /health | 3.1 |
| GET /applications?limit=20 | 9.2 |
| POST /match | 10.0 |
| GET /listings?limit=20 | 12.9 |
| GET /analytics/skills/top (cold) | 8.8 |
| GET /analytics/skills/top (warm) | 5.7 |
| GET /analytics/my-gap | 6.2 |

Method: scripts/bench.py (TestClient + sqlite StaticPool + fakeredis,
mean of 5 runs after warmup; cold = cache cleared first).
Re-run to refresh: `.venv/Scripts/python scripts/bench.py`.
PG + Redis numbers pending Docker on this machine.
