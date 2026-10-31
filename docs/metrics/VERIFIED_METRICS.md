# VERIFIED METRICS — AIDNEXUS ONE (post-repair)

Every currently displayed figure, its verification status, and how it was
independently recomputed. See METRIC_REGISTRY.md for formulas.

| Displayed figure | Where | Status | Independent verification |
|---|---|---|---|
| Total requests 200 | KPI card | ACTUAL, verified | recomputed from registry in `test_counts_consistent_with_requests` |
| Delivered count | KPI card | ACTUAL, verified | same test |
| Dispatched count | KPI card | ACTUAL, verified | same test |
| Critical delivered % | KPI card | ACTUAL, verified | recomputed in `test_critical_fulfillment_counts_delivered_only`; v1 showed 100% with 15/200 delivered (FIXED — now delivered-only) |
| Blocked count + reasons | KPI + Blocked panel | ACTUAL, verified | `test_blocked_work_visible_with_reasons` (identity with plan entries) |
| Queue order & sequence numbers | Dispatch queue | ACTUAL, verified | concordance 1.0; `test_queue_order_matches_plan_sequence`; regression guard against the old insertion-order defect |
| Plan diff (before/after) | Approval banner | ACTUAL, verified | rendered from `replan_delta` computed in `inject_disruption`; no hardcoded values remain |
| Audit hash chain | Evidence ledger | ACTUAL, verified | `test_events_are_hash_chained` (prev-hash linkage) |
| Benchmark cards (all fields) | Benchmark arena | ACTUAL (simulated), verified | `test_benchmark_is_real_simulation` (seed-sensitive), `test_integrity_metrics_zero_violations`, trace-coherence test; artifacts in `benchmarks/results/` |
| Queue concordance % | Header plan badge | ACTUAL, verified | `queue_concordance()` == 1.0 in health + tests |

## NOT MEASURED (displayed nowhere; would be fabrication)

- LLM triage precision/recall (no LLM in build — the old "98.4% precision" claim was removed).
- Real-world delivery performance (simulated scenario only; labeled as such).
- Any production/uptime metric (local demo).

## Rounding & precision policy

Percentages: 1 decimal. Counts: integers. Kilometers: 1 decimal. Latencies:
4 decimals (benchmarks), 1 decimal (UI). No false precision beyond source data.
