# Multi-NGO Workflow Report (Phase IV, Mission C) — IMPLEMENTED + TESTED

## What was built

Cross-organization resource sharing with sequential dual approval, moving real
inventory through the canonical ledger (`persistence.apply_inventory_movement`)
in both organizations, with per-org audit chains and tenant-isolated views.

Code: `backend/app/persistence_phase4.py` (create/approve/dispatch/receive/
cancel/list transfers), `backend/app/main.py` (7 endpoints), migration v3
(`resource_transfers`).

## State machine (enforced inline, tested)

```
PROPOSED → SOURCE_APPROVED → DEST_APPROVED → DISPATCHED → RECEIVED
     ↘ CANCELLED (any pre-dispatch state)
                                  DISPATCHED → FAILED (dispatch-time stock shortfall)
```

## Verified properties (`tests/test_mission_c_e2e.py`, 6 tests)

1. **Ownership + stock validation at proposal**: unknown dest org, same-org,
   insufficient stock → 400 (fail closed).
2. **Sequential dual approval**: destination cannot skip the source step (409);
   source approves as source org, destination approves as destination org;
   a PACIFIC member cannot approve the destination step (403).
3. **Dispatch idempotency**: replayed dispatch rejected (409); exactly one
   `xfr:{id}:out` movement row exists even after replay attempts.
4. **Cancellation**: pre-dispatch cancellation works; cancelled transfers
   cannot be approved (409).
5. **Both-org visibility + audit**: each org lists the transfer; each org's
   audit chain verifies and records its own events only.
6. **Tenant isolation**: non-party actions fail closed; forged org headers
   rejected (security suite).

## Honest limitations

- Transfer facts (item, quantity, status, org ids) are visible to both parties
  by design; no other private data crosses the boundary.
- Transport feasibility is represented by inventory movement only — no
  physical route/vehicle binding for transfers yet (PROPOSED, atlas FLE domain).
- Impact reporting across organizations: each org reports its own side
  (TRANSFER_IN/OUT movements are included in the org impact report); a joint
  cross-org report is PROPOSED.
