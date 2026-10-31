# Phase IV Decision Log

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| D1 | Branch `phase-4-autonomous-operations` from the Phase III head (not main) | Phase III (`2c34e93`) is the verified current implementation; main is 2 phases behind | branching from main (would discard verified work) |
| D2 | Reuse `apply_inventory_movement` for transfers + procurement receipts | one ledger, DB-enforced non-negative stock, idempotency keys | per-domain stock mutation code (duplicate ledger logic) |
| D3 | Sequential dual approval (source → destination) | explicit contract, unambiguous responsibility; destination cannot pre-empt source | parallel approvals (ambiguous veto semantics) |
| D4 | Consent enforcement point = delivery confirmation (409 when revoked); consent REQUIRED at API intake; seeded demo requests carry no consent row | no breakage of the 200-request seeded scenario; honest labeling instead of retroactive fake consent | blocking all seeded deliveries (would break the demo + tests dishonestly) |
| D5 | Intake field sanitization (strip tags/control chars) in addition to frontend escaping | defense in depth: stored data flows to reports/exports; hostile markup never persisted verbatim | relying solely on render-time escaping |
| D6 | Outbox consumer marks events processed without external side effects | no provider exists; claiming external delivery would violate the anti-fabrication policy | pretending messages were sent |
| D7 | No Kubernetes; keep docker-compose | no operational justification at this stage; cloud-native ≠ maximum infrastructure | k8s manifests for the demo's sake |
| D8 | Impact report recomputes from authoritative rows with provenance hash | auditors can verify; cached dashboards invite drift | caching dashboard numbers |
| D9 | Fresh benchmark artifact; committed Phase I artifacts untouched | reproducibility + honesty; losses reported (FIFO wins 3 of 9 runs) | modifying baseline artifacts to look better |
| D10 | UI transfer approvals deferred | half-built approval queues are worse than none (taste = restraint); API + tests cover the flow | shipping untested UI controls |
| D11 | Fix impact report's double-qualified receipt lookup (real bug found by test) | `AidRequestRow.id` is org-qualified; the report must key receipts by the stored qualified id | weakening the missing-evidence assertion |
