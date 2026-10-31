# METRIC REGISTRY — AIDNEXUS ONE

Canonical definitions for every displayed KPI and benchmark metric.
Rule: a metric may only be displayed if registered here. Formula version applies
to the current implementation (v2 formulas post-repair).

## Dashboard KPIs (`/api/v1/state` → `stats`)

| ID | Display name | Formula (v2) | Numerator | Denominator | Source | Status | Test |
|----|--------------|--------------|-----------|-------------|--------|--------|------|
| K1 | Total Aid Requests | `len(requests)` | all requests | — | in-memory registry | ACTUAL | `test_counts_consistent_with_requests` |
| K2 | Delivered (proof recorded) | count of `status == DELIVERED` | delivered requests | — | request registry + receipts | ACTUAL | `test_counts_consistent_with_requests` |
| K3 | Dispatched Missions | count of `status == DISPATCHED` | dispatched requests | — | request registry | ACTUAL | `test_counts_consistent_with_requests` |
| K4 | Critical Requests Delivered (%) | `critical_delivered / critical_total × 100` | CRITICAL **and DELIVERED** | all CRITICAL requests | request registry | ACTUAL (v1 counted DISPATCHED as fulfilled — FIXED) | `test_critical_fulfillment_counts_delivered_only` |
| K5 | Blocked (unmet) | count of plan entries with blocking FeasibilityStatus | blocked plan entries | — | active plan `request_entries` | ACTUAL | `test_blocked_work_visible_with_reasons` |
| K6 | Active Disruptions | count of active disruptions | active disruptions | — | disruption registry | ACTUAL | — |
| K7 | Queue Concordance | matching positions / queue length | queue entries whose relative order equals plan order | active-plan queue entries | plan + projection | ACTUAL (must be 1.0) | `test_queue_order_matches_plan_sequence` |

Notes:
- K4 denominator zero ⇒ 0.0 (explicit, not NaN/hidden).
- K3 label says "Missions", not "Vehicles" (v1 mislabel FIXED).

## Benchmark metrics (`backend/app/benchmark.py`)

Simulation-based; scenario = seed + n_requests; disruption: depot outage (middle depot) + 3.5 km hazard at region center at 40% completion (shared across strategies); inventory scarcity 0.7.

| ID | Metric | Formula | Unit | Test |
|----|--------|---------|------|------|
| B1 | Missions Delivered | count of executed deliveries with sufficient stock | count | `test_metrics_derive_from_trace` |
| B2 | Critical Delivered % | delivered CRITICAL / total CRITICAL × 100 | % | `test_metrics_derive_from_trace` |
| B3 | Travel Distance | haversine legs actually traveled (per-mode model; FIFO = out-and-back) | km | — |
| B4 | Avg Delivery Time | mean(delivery arrival − plan start) over delivered | min | — |
| B5 | On-Time Delivery % | delivered with arrival ≤ deadline / delivered | % | — |
| B6 | Unmet Demand | total − delivered | count | `test_metrics_derive_from_trace` |
| B7 | Disruption Recovery % | affected requests recovered (delivered) / affected | % | `test_recovery_beats_static_on_fulfillment` |
| B8 | Replan Latency | wall-clock solve time of the recovery replan (AIDNEXUS only; baselines report 0.0 — they do not replan; never labeled "AI execution time") | s | `test_aidnexus_replanning_latency_measured` |
| B9 | Planning Time | wall-clock planning phase | s | — |
| B10 | CO2e | km × 0.21 (documented approximation factor) | kg | — |
| B11 | Inventory violations | deliveries executed with insufficient stock (verified, and failed) | count | `test_integrity_metrics_zero_violations` |
| B12 | Capacity violations | loads exceeding vehicle capacity | count | `test_integrity_metrics_zero_violations` |
| B13 | Duplicate dispatches | same request delivered twice | count | `test_integrity_metrics_zero_violations` |

## Retired / corrected metrics

| Old display | Defect | Disposition |
|---|---|---|
| "Critical Need Fulfillment" (counted DISPATCHED) | wrong numerator → showed 100% with 15/200 delivered | replaced by K4 |
| "100% cryptographically signed" | seed deliveries had no signatures | claim removed |
| Benchmark constants (176/118/89, 38.5 min, 0.28 s, 94.2 resilience) | fabricated, seed-insensitive | replaced by B1–B13 computed from traces |
| "hazard_bypass_pct: 100.0" | hardcoded | removed |
| Hardcoded plan diff "174→171 missions" | static HTML | replaced by real `replan_delta` |
| "Urgency NLP Precision 98.4%" | invented copy | removed; classifier has no measured precision → NOT MEASURED |
| "disruption_resilience_score" (dashboard) | undefined formula | only exists as B7 with defined formula |
| Ledger "UTC" label with local time | mislabel | now truly UTC (ISO slice) |
