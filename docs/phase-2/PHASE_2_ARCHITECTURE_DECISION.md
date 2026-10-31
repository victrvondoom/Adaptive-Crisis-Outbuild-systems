# PHASE II ARCHITECTURE DECISION (Milestones 1, 2, 3, 5)

## One source of truth

**The application database (SQLAlchemy 2.0; PostgreSQL in production, SQLite WAL for local/CI) is the single authoritative store for all durable business data.** The optimization engine is a stateless computation service embedded in the same process (invocable externally via the same contracts); it receives validated snapshots and returns versioned computation results (`optimization_run_id`, `plan_version`). No second authoritative database exists; the in-memory simulation actors (vehicles' live positions, sim clock) are explicitly documented as non-authoritative and re-seeded from the deterministic scenario on restart, reconciling against DB truth (`reconcile_from_db`).

### Ownership matrix

| Data | Owner | Notes |
|---|---|---|
| Organizations, users, memberships, sessions | DB (`organizations`, `users`, `memberships`, `sessions`) | tenant scope source of truth |
| Aid requests + items | DB `aid_requests` (org-qualified PK) | engine mirrors for simulation |
| Inventory + movements ledger | DB `inventory_items` + append-only `inventory_movements` | DB CHECK quantity≥0; ATOMIC updates |
| Plan versions + approvals | DB `plan_versions`, `approvals` (full plan JSON snapshots) | queue projects from active version |
| Delivery receipts | DB `delivery_receipts` (UNIQUE request per org) | idempotency anchor |
| Audit events | DB `audit_events` (org-scoped hash chain, UNIQUE seq+hash) | tamper-evident, verified via API |
| Agent executions + tool calls | DB `agent_executions`, `agent_tool_calls` | context envelope persisted per run |
| Outbox events | DB `outbox_events` | transactional outbox, idempotent keys |
| Execution order | optimizer output only (`scheduled_sequence`) | UI renders the projection verbatim |

## Authentication propagation

- Production: OIDC JWT (`identity.ProductionAdapter`; issuer/audience/JWKS; RS256 verified in tests with locally generated keys). NOT ACTIVE — no IdP credentials (BLOCKED, code complete).
- Development: `identity.DevAdapter` — gated by `APP_ENV != production AND DEV_AUTH_ENABLED == 1` (both explicit; fail closed; tested).
- Every request: bearer token → signature/issuer/audience/expiry → DB session liveness (revocable) → membership-derived scopes → `X-Org-Id` only selects among one's own orgs.

## Failure boundaries & consistency

- Engine (simulation) failures never corrupt DB truth; solver failures abort replans with no state change (tested).
- DB write failures during audit mirroring are logged, never crash the operation, and are detectable via `verify_audit_chain`.
- Concurrent delivery/allocation/approval safety is enforced by the DATABASE (unique keys, atomic SQL updates, CHECK constraints) — not only application checks (all concurrency-tested).

## Integration dependencies (honest status)

| Integration | Status |
|---|---|
| PostgreSQL driver & schema | IMPLEMENTED+TESTED (SQLite parity); live Postgres connection BLOCKED (no credentials) |
| Mistral / OpenAI-compatible LLM | Adapter IMPLEMENTED+TESTED (timeouts, retries, JSON mode, schema validation); activation requires API key — BLOCKED, DeterministicProvider honestly labeled |
| OutSystems ODC + MCP | NOT AVAILABLE (no connector/auth in environment); blueprint exists in `outsystems/*.md` + `docs/outsystems-integration.md`; REST surface in `main.py` matches `integration-contracts.md` |
| Twilio | NOT IMPLEMENTED (no credentials); outbox pattern ready for notification delivery |

## Deployment topology (implemented vs. blocked)

- IMPLEMENTED: container image (non-root, healthcheck), compose dev stack (app + PostgreSQL 16), `/healthz`, `/readyz`, JSON logs with X-Request-ID correlation, graceful shutdown, CI workflow with quality gates.
- NOT DEPLOYED: no cloud credentials — manifests are locally tested only; a local container run is NOT claimed as a production deployment.
