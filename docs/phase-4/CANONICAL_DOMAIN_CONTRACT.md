# Canonical Domain Contract (Phase IV, Wave 2)

Single source of truth per canonical object. Every service/API/agent must use
these identifiers, states and ownership rules. Projections are allowed but must
declare their owner and are never authoritative.

| Canonical object | Authoritative owner | Identifier | Lifecycle states | Tenant rule |
|---|---|---|---|---|
| Organization | `organizations` table | `ORG-*` string PK | ACTIVE / SUSPENDED | platform |
| Membership | `memberships` table | surrogate | ACTIVE / REVOKED | per user+org |
| User | `users` table | surrogate + email | live via `sessions` | platform |
| AidRequest | `state_engine` (memory) + write-through `aid_requests` | `{ORG}-{SEQ}` | `MissionStatus` state machine | `org_id` on every row/query |
| Beneficiary consent | `beneficiary_consents` (v3) | `CON-*` | GRANTED / REVOKED | org-scoped, request-bound |
| Inventory | `inventory_items` | (org,depot,item) key | on_hand >= 0, reserved <= on_hand | org+depot scoped |
| InventoryMovement | `inventory_movements` | surrogate, unique `idempotency_key` | append-only ledger | org scoped |
| MissionPlanVersion | `plan_versions` | `PLAN-v{n}` | DRAFT → PENDING_APPROVAL → APPROVED(active) / SUPERSEDED | org scoped |
| Approval | `approvals` | surrogate, binds plan row + approver | append-only | org scoped |
| DeliveryReceipt | `delivery_receipts` | unique per request | one per request (idempotent) | org scoped |
| Disruption | `disruptions` | `DIS-*` | ACTIVE / RESOLVED | org scoped |
| AgentExecution | `agent_executions` | `AE-*` | lifecycle per `agents_runtime` | org scoped |
| AuditEvent | `audit_events` | seq + hash chain | append-only, verifiable | org scoped |
| ResourceTransfer (new, v3) | `resource_transfers` | `XFR-*` | PROPOSED→SOURCE_APPROVED→DEST_APPROVED→DISPATCHED→RECEIVED / FAILED / CANCELLED | dual-org; each side sees only its own view |
| Procurement (new, v3) | `procurements` | `PRC-*` | PROPOSED→APPROVED→ORDERED→RECEIVED / REJECTED / DISCREPANCY | org scoped |
| Supplier (new, v3) | `suppliers` | `SUP-*` | REGISTERED / VERIFIED / SUSPENDED | org scoped |

## Cross-cutting rules

1. **IDs**: uppercase prefix + hyphen + sequence; engine uses qualified request ids `{org}-{request}`, DB stores raw.
2. **Timestamps**: DB rows use timezone-aware datetimes; engine uses epoch seconds; conversions via `persistence_phase3._aware`.
3. **Money**: cents (int) for costs; never floats for currency.
4. **Every mutation**: audit event + (where operationally meaningful) outbox event in the same transaction.
5. **State mutations by agents**: proposals only; a deterministic workflow + human approval commit changes (see AGENT_CONTROL_PLANE.md).
6. **Priority vs execution order**: `urgency_score` (policy) never equals dispatch order; `scheduled_sequence` from the approved plan is the only execution order.
7. **Inventory mutations**: only `persistence.apply_inventory_movement` changes stock; every other path (delivery, transfer dispatch/receive, procurement receipt) routes through it — no duplicate ledger logic.
