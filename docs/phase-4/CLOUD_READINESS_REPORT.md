# Cloud Readiness Report (Phase IV, Wave 10)

Status: IMPLEMENTED + TESTED locally; **DEPLOYED: NO** — no production
deployment was attempted (no authorization, no cloud credentials).

## Existing cloud assets (verified, from Phase II)

- `Dockerfile` (reproducible container build) + `docker-compose.yml`
  (app + durable volume; PostgreSQL via `DATABASE_URL` supported in code).
- Health/readiness: `/healthz`, `/readyz`, `/api/v1/health`.
- Migrations: numbered, transactional, exactly-once (`schema_migrations`);
  Phase IV adds **v3** (consents, transfers, procurements, suppliers, budget).
- Structured JSON logs with correlation ids (`aidnexus.http` middleware).
- CI: `.github/workflows/ci.yml` — gates the full deterministic suite.
- Secure configuration: env-gated secrets (DATABASE_URL, auth adapter,
  LLM provider key); no committed secrets (verified).

## Phase IV additions to the operational picture

- Outbox consumer endpoint (`POST /api/v1/outbox/dispatch`) — event-driven
  reliability now has a runnable dispatcher (idempotent, tested).
- Recovery behavior: disruption → pending recovery plan → human approval —
  exercised end-to-end in Mission B with queue concordance intact.
- Data durability: every Phase IV workflow is write-through persisted; the
  impact report recomputes from durable rows after restarts.

## Honest gaps (BLOCKED / NOT IMPLEMENTED)

- Live PostgreSQL verification: BLOCKED (no credentials) — code path exists,
  unverified against a real server.
- Distributed tracing / metrics backend (OpenTelemetry, Prometheus): NOT
  IMPLEMENTED (structured logs + correlation ids only).
- Backup/restore automation, restore verification: NOT IMPLEMENTED for
  production (documented procedure only).
- Rate limiting / API abuse detection: NOT IMPLEMENTED.
- OutSystems ODC deployment: BLOCKED (no ODC access in this environment).
- Kubernetes: deliberately NOT introduced (no operational justification for
  this product at this stage; docker-compose covers the demo honestly).
