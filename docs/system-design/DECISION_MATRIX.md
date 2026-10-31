# System Design Decision Matrix — Phase V

Decision classes: **A = IMPLEMENT NOW** · **B = PREPARE FOR SCALE** ·
**C = MANAGED BY PLATFORM** · **D = NOT REQUIRED** · **E = BLOCKED**.

Every decision records: problem → actual condition → choice → evidence/test.

| # | Topic | Class | Decision & rationale | Evidence |
|---|---|---|---|---|
| 01 | Rate Limiting | **A** | App-level token-bucket limiter (per identity + per org + anonymous), FastAPI middleware, 429 + `Retry-After`, tenant-isolated so one org cannot starve another. Edge limiter (CDN/gateway) is the production complement — documented, NOT claimed live. | `app/rate_limiter.py`, `tests/test_rate_limiter.py` |
| 02 | Caching | **A (in-process)** | Mtime-keyed cache for the feature atlas (invalidates on file change); TTL micro-cache for hot non-sensitive reads. No Redis: single-process prototype; cache-aside interface prepared for scale (B). | `app/feature_atlas_api.py` `_load()`; `app/rate_limiter.py` TTL reuse; `tests/test_feature_atlas_api.py` |
| 03 | Load Balancing | **C/D** | Single FastAPI service, stateless (tenant state in DB). LB belongs to the hosting platform (ODC/cloud). No app-level LB introduced; health/readiness probes exist for any LB. | `/healthz`, `/readyz`; DEPLOYMENT_TOPOLOGY.md |
| 04 | Reverse Proxy | **C** | TLS termination / static assets handled by the platform in front of the container; uvicorn is never exposed directly in deployment docs. Local dev: FastAPI serves static files (documented dev-only). | `Dockerfile`, docs/deployment.md |
| 05 | API Gateway | **A (single-process gateway layer)** | The FastAPI app IS the single entry point: bearer auth, org scoping, rate limiting, correlation IDs, error normalization, versioned `/api/v1`. No separate gateway product (overlapping gateways rejected). | `app/main.py` middleware + `guard()`; `tests/test_authz_phase2.py` |
| 06 | CI/CD | **A** | GitHub Actions pipeline (lint, tests, P0 gates, browser, benchmark smoke, container build, secret scan). Production deploy requires explicit approval — honestly not configured (no remote until now). | `.github/workflows/ci.yml` |
| 07 | Docker | **A** | Existing multi-service container definition (app + DB volume). Non-root, healthcheck, pinned deps per Phase II. Image ≠ container semantics documented in Studio. | `Dockerfile`, `docker-compose.yml` |
| 08 | Kubernetes | **D** | Explicitly rejected: single service, no autoscaling need, massive overhead (documented in ADR-08). PaaS/compose sufficient. Re-evaluate at multi-service scale. | ADR-08 in DECISION_LOG |
| 09 | Service Discovery | **D (env config)** | All dependencies (DB, provider base URL) resolve via environment configuration — no hardcoded dynamic IPs. No registry service: single-process topology. | `app/db.py` DATABASE_URL, `agents_runtime.resolve_provider` |
| 10 | Circuit Breakers | **A** | Breaker around the LLM provider path (the only external-dependency call: HttpLLMProvider/MistralProvider). CLOSED→OPEN→HALF_OPEN→CLOSED with fallback to deterministic provider — graceful degradation, mission safety preserved. | `app/resilience_patterns.py`, `tests/test_resilience_patterns.py` |
| 11 | Timeouts | **A** | Explicit timeouts: HTTP provider call, benchmark/optimizer watchdog, validator subprocess (60s). No unbounded waits on external calls. | `agents_runtime.py`, `feature_atlas_api.validate()` |
| 12 | Retries | **A** | Classified retry policy: retry only transient (5xx/timeouts), never 4xx auth/validation; bounded attempts + deadline. | `app/resilience_patterns.py` |
| 13 | Exponential Backoff | **A** | Full-jitter exponential backoff (1s→2s→4s…, cap), honored `Retry-After` for 429. | `app/resilience_patterns.py` |
| 14 | Idempotency | **A** | DB-enforced: unique receipts, unique ledger idempotency keys, conflict rejection when key+payload mismatch. | `tests/test_persistence_phase2.py`, `tests/test_phase4_security.py` |
| 15 | Queues & DLQ | **A (DB outbox)** | Transactional outbox (same DB tx) is the durable queue; consumer is idempotent; events exceeding MAX_ATTEMPTS are dead-lettered (inspectable, replayable by admin). Redis/RabbitMQ rejected (operational overhead). | `persistence.py` outbox, `persistence_phase4.dispatch_outbox`, `tests/test_mission_events.py` |
| 16 | Pub/Sub | **B** | Outbox event types are the broadcast contracts; today every consumer is in-process (dispatch marker + audit). A real fan-out bus is prepared-for-scale, not installed. | OUTBOX events in `docs/phase-4/INTEGRATION_MAP.md` |
| 17 | EDA | **B (outbox events)** | Past-tense domain events (AidRequestCreated, TransferDispatched…) with tenant + correlation ids, written transactionally. Event sourcing explicitly rejected (audit chain already provides the immutable log). | outbox payloads; audit chain |
| 18 | Distributed Transactions | **A (single-DB boundaries)** | All multi-org mutations (transfers) happen in ONE database — a single ACID tx spans both orgs' ledger rows. No 2PC anywhere (rejected: locks + slowness). | `persistence_phase4.dispatch_transfer` single-session tx |
| 19 | Saga | **A (state-machine saga)** | The transfer lifecycle PROPOSED→…→RECEIVED/FAILED/CANCELLED is a durable saga: idempotent steps, human approvals, failure paths are compensations (cancel pre-dispatch; FAILED at dispatch leaves both ledgers consistent; nothing erased from audit). Resumable after restart by construction (status persisted per step). | `tests/test_mission_c_e2e.py`, `tests/test_phase4_security.py` |
| 20 | Cron / Scheduled | **A (DB-locked scheduler)** | Durable scheduler table + job registry; `POST /api/v1/scheduler/tick` executes due jobs under a DB row lock → duplicate triggers are no-ops; UTC everywhere; idempotent jobs (outbox recovery, expiry checks, integrity check). No per-replica in-process crontab. | `app/scheduler.py`, migration v4, `tests/test_scheduler.py` |

## Explicitly rejected (class D) — recorded, not merely omitted

- **Kubernetes**: one service; overhead ≫ benefit (Golden Rule applied).
- **Redis / Kafka / RabbitMQ**: outbox + SQLite/Postgres covers current async needs exactly-once-enough; a second durable system would double operational surface.
- **Nginx in-repo**: platform-managed TLS in any real deployment.
- **2PC**: no multi-database writes exist.
- **Event sourcing**: audit hash-chain already provides the immutable fact log.

## BLOCKED (class E)

- Edge/CDN rate limiting, managed LB/proxy behavior, ODC gateway features,
  real LLM latency/breaker telemetry: all require cloud/ODC/LLM credentials
  that do not exist in this environment. Interfaces are prepared and labeled.
