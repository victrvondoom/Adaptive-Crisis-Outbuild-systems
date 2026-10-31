# Phase IV — Repository Intelligence Report (Wave 1)

Branch: `phase-4-autonomous-operations` (created from `feature-expansion-1080` @ `2c34e93`).

## 1. Verified Git baseline (actual, not reported)

| Fact | Verified value |
|---|---|
| main | `0fffb83` (Phase I final) |
| phase-2-production-readiness | `576ee2b` |
| feature-expansion-1080 | `2c34e93` (dynamic atlas) |
| Working tree at Phase IV start | clean |
| `0fffb83` ancestor of Phase IV branch | yes (`git merge-base --is-ancestor` OK) |
| Backend suite at Phase IV start | **183 passed, 9 deselected** (browser marker) |
| Browser suite at Phase IV start | 9/9 journeys green |

## 2. Actual architecture (verified by source inspection)

- `backend/app/main.py` — FastAPI, 37 endpoints, single-origin (serves frontend).
- `backend/app/state_engine.py` — in-memory authoritative operational engine + write-through persistence; plan versioning, hash-chained audit, disruption injection, `get_dispatch_queue()` pure projection.
- `backend/app/optimizer.py` — priority-weighted greedy insertion + priority-preserving 2-opt (HEURISTIC, honestly labeled).
- `backend/app/persistence.py` — SQLAlchemy persistence layer incl. transactional outbox (`enqueue_outbox`/`claim_pending_outbox`), hash-chained audit (`append_audit_event`/`verify_audit_chain`).
- `backend/app/agents_runtime.py` — ContextEnvelope (freshness + plan-version binding), provider abstraction (`DeterministicProvider`, `HttpLLMProvider`, `MistralProvider`), JSON-schema output validation, agent execution + tool-call persistence.
- `backend/app/agents.py` — 3 agents with explicit action contracts (deterministic; no LLM claim).
- `backend/app/authz.py` / `identity.py` — bearer token + `X-Org-Id`, permission matrix, role model, dev identities.
- `backend/app/models_db.py` — 17 ORM tables incl. organizations, memberships, sessions, aid_requests, inventory_items, inventory_movements, plan_versions, approvals, delivery_receipts, disruptions, audit_events, agent_executions, agent_tool_calls, outbox_events.
- Migrations: `app/migrations/versions/v1.py`, `v2.py` (numbered, transactional, exactly-once via `schema_migrations`).
- Frontend: vanilla JS SPA, 7 tabs (mission-command, disruptions, intake, volunteer, benchmarks, ledger, atlas).
- CI: `.github/workflows/ci.yml`; container: `Dockerfile`, `docker-compose.yml`.
- Feature atlas: 1,093 records / 1,080 portfolio / 36 domains, live API + UI (commit `2c34e93`), validator enforced.

## 3. Dead / disconnected / missing findings

1. **No API front door for aid requests.** `AidRequestRow` and `persist_request` exist, but the only request sources are the seeded scenario (`reset_scenario`) and the triage agent internally. There is NO `POST /api/v1/requests` intake endpoint — external intake (Mission A step 1) is not reachable through the API. **Wave 3 target.**
2. **No consent record.** `AidRequestRow` has no consent field/table; beneficiary consent is not captured anywhere. **Wave 3 target.**
3. **Cross-NGO transfer: entirely missing** (no tables, endpoints, tests). Atlas specs exist (ORG domain) but nothing is implemented. **Wave 4 target (Mission C).**
4. **Procurement: entirely missing** (no suppliers, purchase orders, receiving, discrepancies). Atlas specs exist (PRO domain). **Wave 5 target (Mission D).**
5. **Impact report: metrics exist but no evidence-linked mission impact report endpoint** reconciling receipts, inventory movements and audit into a provenance-hashed report. **Wave 6 target (Mission E).**
6. **Outbox events are enqueued but no consumer exists** — `claim_pending_outbox` has no caller in the app runtime (only tests); events accumulate unprocessed. **Wave 9 target.**
7. **`/api/v1/disrupt` + `/replan/approve` implement Mission B's core**, but there is no single end-to-end regression walking warehouse failure + route closure + volunteer cancellation in one run with completed-work preservation assertions. **Wave 6 target.**
8. Root-level `test_api_*.db` litter from pre-`576ee2b` test runs (untracked) — deleted during Wave 1.
9. `docs/` Phase I–III reports remain authoritative; Phase IV adds `docs/phase-4/` without rewriting them.

## 4. Preserved invariants (P0, must not regress)

- Queue concordance 1.0 (`tests/test_queue_concordance.py`).
- Idempotent delivery confirmation (unique receipt per request; inventory deducted once).
- Audit hash-chain verification.
- Tenant isolation on every DB query path (`org_id` scoping + `guard()`).
- Atlas validator gate.
- Benchmark artifacts under `benchmarks/` / `docs/benchmarks/` — never modified to flatter results.
