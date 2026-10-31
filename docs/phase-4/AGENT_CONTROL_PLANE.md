# Agent Control Plane (Phase IV, Waves 7–8 status)

Status labels: IMPLEMENTED / TESTED (executable evidence exists) or BLOCKED.

## Execution lifecycle — IMPLEMENTED + TESTED

`backend/app/agents_runtime.py::run_action` is the single control-plane entry
point for every agent action. Actual enforced lifecycle:

```
CREATED (execution record built)
  → CONTEXT_RESOLVED (ContextEnvelope bound: tenant, actor, role, plan version,
                       policy version, permitted actions, freshness checked)
  → AUTHORIZED (endpoint-level guard() runs BEFORE any agent action)
  → EXECUTING (provider.complete / deterministic handler)
  → VERIFYING (JSON-schema output validation + postcondition vs REAL state)
  → COMPLETED (SUCCEEDED | REVIEW_REQUIRED) or FAILED
```

Exception semantics (tested in `tests/test_agents_runtime.py`, 17 tests):
- Provider failure → record persisted as **FAILED** with error, then raised — no silent success.
- Schema violation → **FAILED** (`SchemaValidationError`).
- Postcondition failure → **FAILED** (`postcondition_ok: false`) — success is defined by verified application state, never model text.
- Human-review required → **REVIEW_REQUIRED** (no auto-activation).

## Separation of concerns — IMPLEMENTED + TESTED

| Concern | Owner | Evidence |
|---|---|---|
| Reasoning / proposal | provider or deterministic handler | agents.py contracts |
| Tool selection | typed action contracts (`docs/agents/AGENT_ACTION_CATALOG.md`) | test_agents.py |
| Tool execution | deterministic handler in `run_action` | test_agents_runtime.py |
| Validation | JSON schema + postcondition check | test_agents_runtime.py |
| Authorization | `guard()` permission check before the action | test_authz_phase2.py |
| Approval | `approve_pending_plan` / Phase IV dual-approval transfers — a model never approves its own consequential action | mission B/C E2E |
| State mutation | engine + persistence in the handler only after checks | queue concordance tests |
| Verification | postconditions against DB + engine | test_agents_runtime.py |
| Audit | hash-chained events per mutation | test_persistence_phase2.py |

## Registry, versioning, budgets, tracing, cancellation — status

- Agent registry: 3 agents with explicit contracts (IMPLEMENTED + TESTED).
- Versioning: prompt_version + context_version recorded per execution (IMPLEMENTED).
- Execution + tool-call persistence: `agent_executions`, `agent_tool_calls` (IMPLEMENTED + TESTED).
- Latency + token accounting fields: recorded when a provider supplies them (IMPLEMENTED for HTTP providers; DeterministicProvider sets zeros — honest).
- Timeouts / retries / cancellation / cost budgets: **NOT IMPLEMENTED** for the deterministic build; required only for real provider inference — BLOCKED (no provider credentials).
- Real model inference: adapter (`HttpLLMProvider`, `MistralProvider`) IMPLEMENTED, **BLOCKED** without API keys. No simulated model success is recorded anywhere.

## Context subsystem (Wave 8) — IMPLEMENTED + TESTED

`ContextEnvelope` resolves: organization, actor + role, mission plan version,
policy version, data snapshot timestamp, evidence references, permitted
actions, provider/model/prompt versions. Freshness validation
(`check_freshness`) rejects stale plan-version / stale-snapshot contexts.
Tenant scoping is enforced before context construction (org_id from the
membership-checked token). Cross-tenant context leakage is regression-tested
(`test_authz_phase2.py`, Phase IV `test_phase4_security.py`).

Context invalidation: contexts are built per-request at action time (never
cached across mutations), so inventory/plan/policy changes cannot be served
from a stale envelope; `check_freshness` additionally guards the boundary.
Context evaluation datasets (retrieval quality, contradiction detection) beyond
the existing freshness/permission tests are PROPOSED (atlas CTX domain).
