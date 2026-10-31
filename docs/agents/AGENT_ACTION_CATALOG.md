# AGENT ACTION CATALOG — AIDNEXUS ONE

Every registered agent action, its contract, and its automated test. An action
is COMPLETE only with a passing test that verifies postconditions — not because
the code ran. No LLM is invoked in the current build; Agent 1 is deterministic
(spec for the model-backed variant: `docs/agent-design.md`).

## AGENT-A1-TRIAGE — Agent 1: Need-to-Mission

| Field | Value |
|---|---|
| Purpose | Raw distress text → structured draft work order |
| Business owner | Intake coordinator |
| Input schema | `TriagePayload` (raw_text ≤4000, requester, lat, lng, sector) |
| Context requirements | Existing requests (for duplicate guard) |
| Allowed tools | classify_urgency, extract_items, check_duplicate, sanitize_text |
| Preconditions | non-empty payload (empty → review draft, no crash) |
| Output schema | `(AidRequest, evidence)` — draft + evidence object |
| Required evidence | per-item `source_text`; `priority_reason`; injection flag |
| Postconditions | request registered with status REQUESTED/UNDER_REVIEW; audit `REQUEST_TRIAGED` with evidence |
| Side effects | request creation only (never inventory, never dispatch) |
| Idempotency | duplicate intakes flagged `duplicate_of_id`, routed to human review — never auto-denied |
| Timeout behavior | n/a (deterministic, no external calls) |
| Escalation | `requires_human_review=True` for: unparsed quantities, injection, duplicates, CRITICAL priority |
| Negative cases | empty text; no quantities; injection payload; duplicate; spam |
| Tests | `tests/test_agents.py::TestAgent1Triage` (7 cases) |
| Benchmarks | scenario presets in UI; deterministic (CI-safe) |

## AGENT-A2-PLAN — Agent 2: Resource Strategist

| Field | Value |
|---|---|
| Purpose | Operational state → feasible plan proposal + approval request |
| Business owner | Mission coordinator |
| Input schema | requests, depots, vehicles, optimizer, version label, blocked sets, preserved ids + committed map |
| Context requirements | current inventory, vehicle fleet, policy version |
| Allowed tools | `OptimizerEngine.solve_allocation` (the ONLY order-decider) |
| Preconditions | active scenario; for replans: current plan exists |
| Output schema | `(MissionPlanVersion, interpretation)` |
| Required evidence | optimization_run_id, policy_version, blocked_reasons, solve_time |
| Postconditions | every plannable request has a plan entry (`coverage_complete`); plan NOT active/approved |
| Side effects | plan object only; activation requires human approval |
| Idempotency | same inputs ⇒ identical plan (deterministic; tested) |
| Timeout behavior | heuristic is <10 ms at 500 requests; no timeout path needed |
| Escalation | blocked requests surfaced with reasons; approval_request emitted |
| Negative cases | infeasible stock (BLOCKED_NO_STOCK), capacity (BLOCKED_NO_CAPACITY), hazard (BLOCKED_HAZARD), deadline overrun (flagged) |
| Invariant | Agent 2 never reorders the optimizer's plan (`test_plan_order_is_optimizer_output`) |
| Tests | `tests/test_agents.py::TestAgent2ResourceStrategist` (4 cases) + optimizer suite |

## AGENT-A3-ASSESS — Agent 3: Recovery & Accountability

| Field | Value |
|---|---|
| Purpose | Disruption → impact assessment + preservation set + replan proposal |
| Business owner | Operations reliability |
| Input schema | disruption, current plan, requests_by_id |
| Context requirements | active plan; committed (dispatched/in-transit) assignments |
| Preconditions | active approved plan |
| Output schema | assessment dict (affected/preserved ids, hazard_radius_km, narrative) |
| Required evidence | preserved vs affected lists; radius used |
| Postconditions | completed deliveries never in affected set; `affected_missions` recorded on disruption |
| Side effects | none alone; paired with AGENT-A2-PLAN (replan) which stays approval-gated |
| Idempotency | repeated assessment of the same disruption yields the same sets |
| Negative cases | disruption with no affected missions; disruption flooding a depot with in-flight loads; delivered missions in plan |
| Tests | `tests/test_agents.py::TestAgent3Recovery` (2 cases) + `test_state_machine.py` plan/versioning suite |

## Supporting system actions (agent-adjacent)

| Action | Executor | Postcondition verified by |
|---|---|---|
| SYS-DELIVERY-CONFIRM | `state_engine.confirm_delivery` | `TestIdempotentDelivery` — receipt + single stock deduction + audit |
| SYS-TRANSITION | `state_engine.transition_mission` | `TestTransitions` — legality, terminal states, DELIVERED via confirm only |
| SYS-APPROVE-PLAN | `state_engine.approve_pending_plan` | `TestPlanVersioning` — activates pending only; audited; immutable deliveries preserved |
| SYS-SIM-DELIVERY | `advance_simulation` waypoint arrival | `test_sim_delivery_logs_audit` — deterministic waypoint mapping + audit event |

## Action-level evaluation summary (Level A/B/C)

- **Level A (action correctness):** enforced by the contract tests above — correct
  tool use (optimizer invocation paths), schema-valid outputs (Pydantic), evidence
  present, precondition/postcondition verification, escalation correctness. PASS (deterministic).
- **Level B (agent benchmarks):** task success = postconditions hold (100% in suite);
  tool-call efficiency n/a (no LLM); human-escalation correctness = review flags (tested).
- **Level C (system benchmarks):** `docs/benchmarks/FINAL_BENCHMARK_REPORT.md` —
  mission success, recovery quality, duplicate side effects (0), audit completeness.

## Not implemented (documented honestly)

- Model-backed triage (Bedrock/Azure), tool-permission server, token/cost
  accounting, real-model evaluation suite: NOT_IMPLEMENTED (no credentials);
  spec preserved in `docs/agent-design.md`.
