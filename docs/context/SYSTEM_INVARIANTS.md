# SYSTEM INVARIANTS — AIDNEXUS ONE

Invariants that must hold at all times. Violations are P0. Each is enforced by
at least one automated test (referenced).

## Planning & queue

1. **Optimizer authority:** the active approved `MissionPlanVersion` is the only
   source of execution order. UI queue = pure projection (`get_dispatch_queue`).
   → `tests/test_queue_concordance.py`
2. **No hidden work:** every plannable request appears in `request_entries` as
   SCHEDULED, COMMITTED_PRESERVED, or blocked with an explicit reason.
   → `test_optimizer.py::test_every_request_has_an_entry`
3. **Feasibility:** accepted assignments never violate depot inventory or vehicle
   capacity. → `TestFeasibility`
4. **Priority semantics:** humanitarian priority (`urgency_score` under
   `POLICY_VERSION`) never crosses priority classes (bounded affected-people
   tie-break). Within a route, 2-opt may never move a higher-priority stop later.
   → `TestPriorityAndOrder`
5. **Commitment preservation:** delivered and in-flight missions are immutable
   across replans; preserved entries keep their vehicle/depot.
   → `TestDeadlinesAndPreservation`, `test_delivered_requests_immutable_across_replan`
6. **Approval gate:** no plan after v1.0 becomes active without human approval;
   v1.0 is auto-activated only by the documented SYSTEM BOOTSTRAP and labeled as such.
7. **Stale plans:** the dispatch queue references only the active plan version.
   → `test_queue_entries_belong_to_active_plan`

## State machine

8. **Legal transitions only:** `ALLOWED_TRANSITIONS` is exhaustive; DELIVERED and
   CANCELLED are terminal; DELIVERED can only be set via delivery confirmation.
   → `tests/test_state_machine.py`
9. **Idempotent delivery:** confirming a delivery twice returns the same receipt
   and deducts inventory exactly once. → `TestIdempotentDelivery`
10. **No duplicate dispatch:** a request never appears on two vehicles in one plan.
    → `test_no_duplicate_dispatch_assignments`

## Agents

11. **Agents never deny assistance:** Agent 1 output is always a draft
    (REQUESTED/UNDER_REVIEW); rejection is a human decision.
    → `test_agent_never_denies_assistance`
12. **No invented data:** every extracted quantity carries `source_text` evidence;
    unparsed messages produce empty item lists + review flag.
    → `test_missing_quantities_never_invented`
13. **Injection defense:** instruction-like patterns are stripped from beneficiary
    text before storage. → `test_prompt_injection_sanitized`
14. **Hazard radius authority:** Agent 3 and the optimizer use
    `disruption.hazard_radius_km`, never a constant.
    → `test_uses_disruption_hazard_radius`
15. **Agent 2 never reorders:** its returned plan order equals the optimizer's
    direct output. → `test_plan_order_is_optimizer_output`

## Measurement

16. **Fulfilled = delivered:** dispatch does not count as fulfillment.
    → `test_critical_fulfillment_counts_delivered_only`
17. **Benchmarks are computed, never hardcoded:** seed-sensitive and deterministic
    for a fixed seed; integrity violations must be zero.
    → `test_benchmark_is_real_simulation`, `test_integrity_metrics_zero_violations`
18. **Metric coherence:** fulfilled + unmet == total; critical % consistent with counts.
    → `test_metrics_derive_from_trace`
19. **Recovery must not underperform static planning** on the same scenario.
    → `test_recovery_beats_static_on_fulfillment`

## Audit

20. **Hash chain:** every event's hash includes the previous event's hash; every
    consequential action (plan, approval, delivery, transition, disruption) logs
    an event. → `test_events_are_hash_chained`, `test_audit_coverage_of_key_events`
