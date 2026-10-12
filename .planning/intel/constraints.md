# Intel: Constraints

- **Tech stack**: Fixed per AGENTS.md SPEC (see decisions.md §1). Ask before adding
  a dependency, changing the stack, or deleting files.
- **Scope discipline**: Build only the phase asked for; log ideas to `docs/BACKLOG.md`.
  Tiny/default/high-stakes tiering per harness gates does not override PRD phases.
- **Out of scope (hard)**: App Dockerfile, CI/CD, cloud deploy, Terraform/K8s,
  Prometheus/Grafana, load-test infra, auto-apply, forbidden scraping, polished
  frontend, multi-org/billing, resume file generation.
- **Security**: No plaintext passwords; hash tokens/keys; per-user isolation tested
  adversarially; no secrets in git; CORS + validation review in Phase 5.
- **Data honesty**: No invented README metrics — only measured numbers
  (coverage, benchmark timings, EXPLAIN ANALYZE, extraction precision/recall).
- **Working agreement**: Plan first; one feature per step (`feat(scope): msg`);
  tests with every feature (≥80%); `make lint test` green; type hints, docstrings
  on services, no dead code, no giant functions.
- **Definition of done (per phase)**: code + tests + migration + README section +
  `docs/DECISIONS.md` update + conventional commits.
