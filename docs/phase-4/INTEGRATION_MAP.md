# Integration Map (Phase IV)

How every Phase IV capability connects to the rest of the platform — one
coherent operating environment, no isolated features.

```
API intake (POST /requests)
  ├─ validates against canonical item taxonomy (optimizer/models)
  ├─ records consent (beneficiary_consents) — enforced at delivery confirm
  ├─ duplicate rule = Agent 1's canonical check (agents.check_duplicate)
  ├─ creates the request in THE engine (single source of truth) + write-through DB
  ├─ enqueues AidRequestCreated (outbox) → /outbox/dispatch (idempotent)
  └─ audit chain (hash-linked)

Optimizer (unchanged, preserved asset)
  └─ plans include API-intake requests identically to seeded ones
     → human approval (replan/approve) → dispatch queue (pure projection)

Delivery confirmation
  ├─ consent check (revoked → 409)
  ├─ idempotent receipt (delivery_receipts, unique per request)
  └─ inventory ledger movement (apply_inventory_movement, idempotency key)

Cross-NGO transfer (POST /transfers …)
  ├─ validates source stock via the same inventory tables
  ├─ dual approval (source org → dest org), cancel/fail paths
  ├─ dispatch = two ledger movements (xfr:{id}:out / :in), idempotent
  ├─ per-org audit chains
  └─ visible in org impact reports (TRANSFER_IN/OUT movements)

Procurement (POST /procurements …)
  ├─ supplier registry + verification gate
  ├─ budget check against org budget (v3 column)
  ├─ receipt = ledger movement (proc:{id}:receipt), idempotent
  ├─ discrepancy state when received ≠ ordered
  └─ feeds org impact report (inventory_gained_by_replenishment)

Impact report (GET /impact/report)
  ├─ recomputes from requests + receipts + movements + audit chain
  ├─ formulas explicit (metric registry), actual vs estimated explicit
  └─ provenance sha256 over canonical JSON

UI (NGO Workflows tab)
  └─ renders backend projections only: intake → work order, transfers list,
     procurement list, live impact report (escaped, aria-labelled)

Agent runtime (unchanged)
  └─ ContextEnvelope + run_action with postconditions; triage agent still
     serves unstructured intake; deterministic provider (real LLM BLOCKED)
```
