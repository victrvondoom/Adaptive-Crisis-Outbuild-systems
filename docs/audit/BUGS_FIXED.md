# BUGS FIXED — AIDNEXUS ONE

Every fixed defect: evidence → root cause → fix → regression test.
Original reproduction outputs are in `docs/audit/INITIAL_REPOSITORY_STATE.md`.

## P0

| # | Defect (evidence) | Root cause | Fix | Regression test |
|---|---|---|---|---|
| B1 | UI queue ≠ optimizer plan (plan first-10 all CRITICAL; UI queue mixed LOW/MEDIUM) | Frontend rendered `requests.slice(0,45)` insertion order; no plan projection existed | `get_dispatch_queue()` pure projection of active plan; frontend renders verbatim | `test_queue_concordance.py` (6 tests incl. regression guard) |
| B2 | Duplicate delivery confirmation double-deducted inventory (12000→11628→11256) | No pre-state check in `confirm_delivery` | Receipt store; repeat confirm returns receipt flagged duplicate, deducts once | `TestIdempotentDelivery`, API idempotency test |
| B3 | "Critical fulfillment 100%" with 15/200 delivered | Numerator counted DISPATCHED as fulfilled | Delivered-only numerator; zero-denominator explicit | `test_critical_fulfillment_counts_delivered_only` |
| B4 | `preserve_request_ids` ignored while explanation claimed "Preserved 1 commitments" | Unimplemented parameter + fabricated narrative | Committed assignments carried into plan as COMMITTED_PRESERVED entries | `test_preserved_requests_keep_assignment_and_immutable_status` |
| B5 | `/missions/transition` accepted any transition (attacker → DELIVERED 200 OK) | No state machine | `ALLOWED_TRANSITIONS` + DELIVERED-only-via-confirm | `TestTransitions` + API 400 tests |
| B6 | Benchmark 100% hardcoded (seed 42 ≡ seed 999) | Constants instead of simulation | Real 4-strategy execution-trace engine | `test_benchmark_is_real_simulation` + integrity tests |
| B7 | Stored XSS via innerHTML of API-controlled strings | No escaping in render paths | `escapeHtml()` everywhere + API payload hardening | `test_disruption_payload_hardened` + render-path review |
| B8 | Frontend triage URL doubled (`/api/v1/api/v1/...`) → always 404 → silent fake fallback | API_BASE already contained `/api/v1` | Fixed path; offline state explicit; no local fake results | `test_triage_works_on_canonical_path`, `test_frontend_path_no_longer_doubled` |
| B9 | Second disruption silently overwrote pending plan; only "v2.0" ever approvable | Hardcoded version string | Sequential versions; supersede-with-audit; approval targets pending version | `TestPlanVersioning`, `test_second_disruption_creates_next_version` |
| B10 | Unconstrained 2-opt delayed CRITICAL stops past disruption (found by honest benchmark: 3 critical deliveries lost) | Distance-only route improvement | Priority-preserving 2-opt (monotonic urgency constraint) | `test_two_opt_improves_distance_and_preserves_priority_order` |
| B11 | AIDNEXUS replan double-counted in-flight stock (3 inventory violations, caught by own integrity metric) | In-flight stock deducted after replan snapshot | Deduct before snapshot; stock-insufficient recovery deliveries FAIL | `test_integrity_metrics_zero_violations` |
| B12 | Benchmark disruption timing differed per strategy (unfair comparison) | t_disrupt derived per-mode from own schedule | Shared disruption time from optimized plan | benchmark determinism/pairing tests + report |

## P1

| # | Defect | Fix | Test |
|---|---|---|---|
| B13 | `/state` truncated 200→140 requests silently | Full list returned | `test_state_returns_all_requests` |
| B14 | Volunteers never assigned (12/0) | Role-matched assignment on plan application | `TestVolunteers` |
| B15 | Audit "chain" was per-event hashes; >300 events silently dropped; UI claimed "cryptographically chained and immutable" | Real prev-hash chaining; retention 5000 documented; UI copy honest | `test_events_are_hash_chained` |
| B16 | `advance_simulation` deliveries had no audit events | `_record_delivery` used by sim path too (chained event) | `test_sim_delivery_logs_audit` |
| B17 | Agent 3 + replanning hardcoded 3.5 km radius | Uses `hazard_radius_km` | `test_uses_disruption_hazard_radius` |
| B18 | Plan v1.0 auto-approved as fake human "Lead Mission Coordinator" | `auto_approved=True` SYSTEM BOOTSTRAP, labeled in UI + audit | versioning tests |
| B19 | Agent 1 invented default items (50 L + 20 MRE) when nothing parsed; docstring claimed "Duplicate Guard" (absent) | Empty items + review flag; real duplicate guard; evidence per item | `test_missing_quantities_never_invented`, `test_duplicate_intake_flagged_not_denied` |
| B20 | `hazard_bypass_pct: 100.0` fabricated in replan_delta | Computed delta fields only | API flow tests |
| B21 | Hardcoded plan-diff table "174→171" | Rendered from real `replan_delta` | `renderApprovalDiff` + API tests |
| B22 | Deadline blindness (CVRPPDTW claimed, deadlines unused) | Arrival vs deadline computed; overruns flagged in explanation | `test_deadline_infeasibility_flagged` |
| B23 | Optimizer docstrings claimed "MIP/VRP" and "2-opt" falsely | Honest heuristic description; 2-opt actually implemented (priority-preserving) | docstring + behavior tests |
| B24 | README/docs claimed OR-Tools, ODC, Bedrock, Twilio, tests/, benchmarks/, services/ dirs that don't exist | README rewritten to actual state; status ledger in CURRENT_STATE.md | — |
| B25 | Offline UI fabricated missions/stats/audit-hashes under "LIVE" badge | Explicit OFFLINE state; zero fabrication offline | render-path review |
| B26 | Ledger "UTC" label with local time; blocking `alert()` feedback | True UTC; aria-live toasts | render-path review |
| B27 | CORS `*` + credentials | Restricted same-origin, credentials off | middleware review |
| B28 | Fabricated UI claims (98.4% precision, 12 sensors, "double-dispatch lock ENGAGED") | Replaced with actual running components | — |
| B29 | Waypoint delivery matched by proximity (±0.005°), risk of misattribution | Deterministic waypoint-index→request mapping | `test_sim_delivery_logs_audit` |
| B30 | No requirements.txt / no tests / no pytest config | Added all; 81 tests | suite |
