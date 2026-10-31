# Implementation Matrix (Phase V)

Topic → owning module → live wiring → automated test. A topic is IMPLEMENTED
only if all three columns are non-empty.

| # | Topic | Owning module | Live wiring | Test |
|---|---|---|---|---|
| 01 | Rate limiting | `app/resilience_patterns.py` (RateLimiter) | `main.py` rate_limit_middleware on every /api/v1 route | `tests/test_rate_limiter.py` (15) |
| 02 | Caching | `app/feature_atlas_api.py` | mtime-keyed registry cache (auto-invalidating) | `tests/test_feature_atlas_api.py` |
| 03 | Load balancing | platform-managed (decision C/D) | `/healthz`, `/readyz` for any LB | `tests/test_api.py` |
| 04 | Reverse proxy | platform-managed (decision C) | deployment docs; dev-only direct uvicorn | — (documented) |
| 05 | API gateway | `main.py` middleware + `authz.guard` | authn, org scoping, correlation ids, 429, JSON errors | `test_authz_phase2.py` |
| 06 | CI/CD | `.github/workflows/ci.yml` | lint → 256 tests → P0 gates → browser → container → secrets | CI workflow itself |
| 07 | Docker | `Dockerfile`, `docker-compose.yml` | non-root, healthcheck, DB volume, pinned deps | CI container build |
| 08 | Kubernetes | — (NOT REQUIRED, ADR-08) | rejected | decision record only |
| 09 | Service discovery | env config (`db.py`, `agents_runtime`) | DATABASE_URL / provider env, no hardcoded IPs | config validation |
| 10 | Circuit breaker | `app/resilience_patterns.py` | wraps HTTP LLM provider calls (`agents_runtime`) | `test_resilience_patterns.py` |
| 11 | Timeouts | `agents_runtime` (20s), `feature_atlas_api` (60s), `db.py` (busy 10s) | every external call bounded | retry/breaker tests |
| 12 | Retries | `app/resilience_patterns.py` | classified: transient only, max attempts | `test_resilience_patterns.py` |
| 13 | Backoff + jitter | `app/resilience_patterns.py` | full jitter [0, min(cap, base·2^n)]; Retry-After honored | jitter-bounds test |
| 14 | Idempotency | `persistence.py` unique keys | receipts, ledger movements, transfers, procurement | `test_persistence_phase2.py`, `test_phase4_security.py` |
| 15 | Queue + DLQ | `persistence.py` outbox + `persistence_phase4.dispatch_outbox` | same-tx enqueue; idempotent consumer; dead-letter at 5 | `test_resilience_patterns.py`, `test_mission_events.py` |
| 16 | Pub/Sub | outbox event contracts (PREPARED) | fan-out consumers documented; broker not installed | event contract tests |
| 17 | EDA | outbox event types | past-tense events, tenant + correlation ids | mission E2E suites |
| 18 | Distributed tx | `persistence_phase4.dispatch_transfer` | single ACID tx spans both orgs' rows; no 2PC | `test_mission_c_e2e.py` |
| 19 | Saga | `persistence_phase4` transfer lifecycle | durable steps, human approvals, compensation paths | `test_mission_c_e2e.py`, security suite |
| 20 | Cron | `app/scheduler.py` + migration v4 | DB-claimed jobs, UTC, idempotent, failure-recorded | `tests/test_scheduler.py` (9) |
