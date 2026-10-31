# Service Ownership Map (Phase IV)

AIDNEXUS ONE is a modular monolith: one deployable backend, strictly layered.
"Owner" = the only module allowed to write the object.

| Module | Owns (writes) | Reads |
|---|---|---|
| `state_engine.py` | in-memory request/plan/assignment state (write-through) | optimizer output, DB snapshot |
| `optimizer.py` | plan candidate computation | engine request/vehicle/depot snapshot |
| `persistence.py` | organizations, users, memberships, sessions, aid_requests, depots, inventory, movements, receipts, plan_versions, approvals, disruptions, audit, outbox | everything it owns |
| `persistence_phase3.py` | case_notes, delegations, expiry/certification columns | inventory, volunteers |
| `persistence_phase4.py` (new) | beneficiary_consents, resource_transfers, procurements, suppliers, impact reports | receipts, movements, inventory, audit |
| `agents_runtime.py` | agent_executions, agent_tool_calls | context sources (read-only) |
| `feature_atlas_api.py` | none (read-only projection of JSONL) | atlas registry |
| `frontend/` | nothing (renders backend projections verbatim) | API JSON |

## External integration ownership (honest status)

- **OutSystems ODC** — BLOCKED: no authenticated MCP/ODC access in this environment; REST contracts prepared (docs/outsystems-integration.md). Never claimed live.
- **LLM provider** — adapter exists (`agents_runtime.resolve_provider`: Deterministic by default, Mistral/HTTP when env credentials present). Real inference BLOCKED without keys; no simulated success is recorded.
- **Notifications** — no provider credentials; the system never claims a message was sent.
- **Database** — SQLite (dev/CI) / PostgreSQL via `DATABASE_URL` (production-ready code path, unverified against a live Postgres: BLOCKED by missing credentials).
