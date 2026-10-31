# Feature Gap Reconciliation (Phase IV)

## Gaps selected for Phase IV (high-value, dependency-unblocked)

1. **Intake API + consent + dedup (Mission A)** — the product lacked a real front door for requests; intake existed only through the seeded scenario.
2. **Cross-NGO transfers (Mission C)** — nothing existed; core differentiator for multi-NGO coordination.
3. **Procurement-to-inventory (Mission D)** — replenishment loop missing; inventory depletion had no answer.
4. **Impact report with provenance (Mission E)** — evidence existed but was never reconciled into an auditor-ready report.
5. **Outbox consumer** — events were enqueued with no dispatcher (silent accumulation).
6. **Single E2E regression for the full recovery workflow (Mission B)** — components existed and were individually tested, but no one test walked the full chain.

## Gaps explicitly NOT attempted in Phase IV (with reasons)

- 781 PROPOSED atlas features: specifications only; implementation continues in prioritized waves per `docs/product/FEATURE_ROADMAP.md`.
- ODC native workflows: BLOCKED (no authenticated MCP/ODC access in this environment).
- Real LLM inference: BLOCKED (no provider credentials).
- Notifications (SMS/email/voice): no provider credentials; the system never claims messages were sent.
- Predictive/forecasting features: require real time-series data; deterministic rules must not be labeled AI predictions (anti-fabrication policy).

## Overlaps found and resolved

- **Priority**: `urgency_score` (humanitarian policy) vs `scheduled_sequence` (execution order) — already canonical; re-documented in CANONICAL_DOMAIN_CONTRACT.md.
- **Inventory mutation paths**: only `apply_inventory_movement` changes stock; procurement receiving and transfer dispatch/receive route through it — no duplicate ledger logic.
- **Impact metrics**: the report recomputes from receipts/movements/audit using the metric registry formulas rather than caching dashboard values.
