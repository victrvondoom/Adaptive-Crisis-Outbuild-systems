# Database Design & Normalization (Topic 21)

Source of truth: `backend/app/models_db.py` + migrations v1–v5. Engine under test: SQLite 3.53 (disposable DBs). PostgreSQL not measured.

## Entity mapping (requested entity → actual implementation)

| Requested | Actual table / representation | Status |
|---|---|---|
| Organization | `organizations` | IMPLEMENTED |
| Membership | `memberships` UNIQUE(user_id, org_id) | IMPLEMENTED |
| BeneficiaryReference | no table; `aid_requests.requester_name` + `beneficiary_consents(org_id, request_id)` | **PARTIAL** — no stable beneficiary identity; duplicates handled by `duplicate_of_id` heuristic |
| AidRequest | `aid_requests` | IMPLEMENTED |
| AidRequestItem | `aid_requests.items` **JSON column** | **Denormalized by choice**: items are an immutable evidence snapshot (Agent 1 `source_text`). Consequence: no FK/SQL aggregation per item type |
| Warehouse | `depots` (UNIQUE(org_id,id)) | IMPLEMENTED |
| InventoryItem | `inventory_items` UNIQUE(depot,item), CHECK qty>=0 | IMPLEMENTED |
| InventoryMovement | `inventory_movements` (append-only ledger, UNIQUE idempotency_key) | IMPLEMENTED |
| Volunteer / Vehicle | `volunteers`, `vehicles` | IMPLEMENTED |
| Mission | lifecycle of an `aid_requests` row (state machine) | no separate table |
| MissionAssignment / Dispatch | inside plan payload + request status | no separate table |
| MissionPlan | `plan_versions` UNIQUE(org_id, version_id) | IMPLEMENTED |
| Approval | `approvals` | IMPLEMENTED |
| DeliveryReceipt | `delivery_receipts` (PK = org-qualified request id ⇒ one receipt per request) | IMPLEMENTED |
| AuditEvent | `audit_events` UNIQUE(org,seq), UNIQUE(org,sha256), hash chain | IMPLEMENTED |

## ER diagram (as implemented)
```
organizations 1─* memberships *─1 users
organizations 1─* depots 1─* inventory_items
                       depots 1─* inventory_movements   (ledger; no cascade → blocks depot delete)
organizations 1─* aid_requests ─(logical)─ delivery_receipts, beneficiary_consents
organizations 1─* plan_versions 1─* approvals
organizations 1─* audit_events (hash chain per org)
organizations 1─* agent_executions 1─* agent_tool_calls
organizations 1─* vehicles | volunteers | disruptions | outbox_events | procurements | resource_transfers
scheduled_jobs (global; lease + fence)
```
## Authoritative facts
- Current stock: `inventory_items.quantity`; ledger must reconcile (verified in restore lab).
- Execution order: active `plan_versions` payload (AGENTS.md P0) — queue is a projection.
- Delivered: `delivery_receipts` row. Audit: `audit_events` chain.
- Read models: dispatch queue (projection of plan); no materialized tables.

## Tenant isolation
Every tenant table has `org_id` FK ON DELETE CASCADE; request/depot ids are org-qualified strings (`ORG:ID`). **Gap (P2, OPEN_ISSUES O-1):** `inventory_items.org_id` is not constrained to equal `depots.org_id` (single-column FK). The probe proves the DB accepts an org-B row on an org-A depot; only the application prevents it. Remedy: composite FK `(depot_id, org_id) → depots(id, org_id)` via expand/contract (add unique on depots(id,org_id) — already `uq_depot_org_id` ordered (org_id,id) — then add FK, backfill-verify, enforce).

## Verified behaviours (lab `integrity`, 6/6 as expected)
invalid FK rejected · duplicate membership rejected · negative stock rejected · duplicate idempotency key rejected · cross-tenant row ACCEPTED (documented gap) · depot with ledger history cannot be deleted.
Concurrency: see CONSISTENCY_MODEL. Migration correctness: v5 applied on fresh and pre-v5 DB and idempotent (tests).
