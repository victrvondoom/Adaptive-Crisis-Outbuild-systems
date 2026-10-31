# CONSOLIDATED AUDIT FINDINGS — AIDNEXUS ONE (Pre-Repair)

**Method note:** The audited codebase is ~2,000 source lines (backend 1,362 LOC, frontend JS 1,122 LOC, plus markup/CSS). The auditing agent read **100% of the source** and reproduced every critical finding by execution (see `INITIAL_REPOSITORY_STATE.md` §3) before writing this report. Given complete main-agent source coverage, the five specialist audits below were performed sequentially by the main agent rather than delegated to subagents that would re-read the same small corpus; subagent delegation is reserved for implementation-independent work. Every finding carries file:line evidence and a reproduction method. Nothing below is hypothesis — all P0/P1 items were reproduced.

---

## SPECIALIST AUDIT A — SOFTWARE & ARCHITECTURE

| ID | Location | Finding | Severity | Root cause | Impact | Correction |
|---|---|---|---|---|---|---|
| A1 | `backend/app/benchmark.py:29-56` | Entire benchmark is literal constants; `rng` created, never used; docstring claims "reproducible, anti-fabrication" | P0 | Benchmark never wired to optimizer | All benchmark claims in UI/README are fiction | Replace with real simulation harness calling the actual planner (done — see `benchmark.py` v2) |
| A2 | `backend/app/optimizer.py:14,17` | Docstring claims "CVRPPDTW-MD" and "local 2-opt route improvement"; implementation is greedy insertion, no 2-opt, no time windows | P1 | Docs/code drift | Misleads judges & maintainers about solver capability | Implement 2-opt; implement deadline feasibility; rename honestly |
| A3 | `backend/app/optimizer.py:73` | `preserve_request_ids` accepted, silently ignored | P0 | Unimplemented parameter | Replans may drop committed deliveries; explanation lies about it | Exclude preserved IDs from reassignment and keep their original assignment |
| A4 | `backend/app/agents.py:2-7` | Docstring claims 3 agents; only 2 classes exist; "Duplicate Guard" claimed, never implemented | P1 | Aspirational docstring | Agent 2 is fictional; duplicate intakes accepted | Implement `ResourceStrategistAgent` + duplicate guard |
| A5 | `backend/app/main.py:196-213` | `/missions/transition` allows ANY status→status, no state machine, no authorization, `DELIVERED` via this path skips inventory deduction & timestamp | P0 | No transition validation | State corruption; inconsistent DELIVERED records (two semantic variants) | Enforce allowed-transition table + per-transition side effects |
| A6 | `backend/app/state_engine.py:395-403` (`confirm_delivery`) | Not idempotent: 2nd confirm re-deducts stock and logs again | P0 | No pre-state check | Inventory corruption (reproduced: 12000→11628→11256) | Return existing receipt on repeat; deduct once |
| A7 | `backend/app/state_engine.py:305-370` (`inject_disruption`/`approve_replan`) | Plan version hardcoded `"v2.0"`; 2nd disruption overwrites pending plan; replan approval applies via hardcoded ID | P0 | Version scheme is a string, not a counter | Approval applies to the wrong plan; multiple disruptions lose data | Sequential versioning; approval targets current pending version |
| A8 | `backend/app/state_engine.py:132-137` | Plan v1.0 auto-approved by code as "Lead Mission Coordinator" | P1 | Bootstrap shortcut contradicts human-gate policy | Trust claim broken | Mark as system-bootstrap approval, label honestly, require human approval for all subsequent plans |
| A9 | `backend/app/state_engine.py:526` | `requests: all_reqs[:140]` — silent truncation of 200→140 | P1 | Arbitrary UI perf cap | 30% of missions invisible | Return full set (payload is small) |
| A10 | `backend/app/state_engine.py:250-300` | `advance_simulation` delivers + deducts stock with **no audit event** | P1 | Missing instrumentation | Audit coverage < 100%; ledger misses deliveries | Log DELIVERY_CONFIRMED (SYSTEM actor) event |
| A11 | `backend/app/agents.py:97` | Hardcoded `3.5` km hazard radius; ignores `disruption.hazard_radius_km` | P1 | Magic number duplication | Recovery assessment inconsistent with disruption spec | Use the model field |
| A12 | `backend/app/state_engine.py:57-72` | Audit "hash" is per-event, not chained; buffer silently drops >300 events | P1 | Overstated "immutable chained ledger" claim | Tamper-evidence claim is false | Chain hashes (include prev hash); document retention |
| A13 | `frontend/js/app.js:616` | `fetch(\`${API_BASE}/api/v1/nlp/triage\`)` = `/api/v1/api/v1/nlp/triage` → 404 always; silent fallback to fake local parser | P0 | Path duplication | Agent 1 never actually invoked from UI | Fix URL; make fallback explicit |
| A14 | `frontend/js/app.js:24-115` (`initFallbackState`) | Entire parallel client-side simulation with fabricated audit hashes (`"a94a8fe..."` constants) and stats; header shows "LIVE NETWORK" even when disconnected | P1 | Demo resilience feature presented as live | Users cannot distinguish real vs fabricated state | Explicit connection banner; remove fake hashes |
| A15 | `backend/app/main.py:27-33` | CORS `*` + credentials | P2 | Copy-paste middleware | Credential leakage pattern (demo scope) | Same-origin serving makes this unnecessary; restrict |
| A16 | Repo | No `requirements.txt`, no tests, no CI, no lint config; README structure (`services/`, `tests/`, `benchmarks/`) fictional | P1 | Incomplete scaffolding | Unreproducible environment | Add requirements + test suite |
| A17 | `backend/app/state_engine.py` vehicle delivery matching `abs(lat diff)<0.005` | Two requests within ~550 m can be confused on arrival; `break` after first match | P2 | Loose proximity match | Possible misdelivery attribution in sim | Match by waypoint index→request mapping |

## SPECIALIST AUDIT B — OPTIMIZATION & PRIORITY QUEUE SCIENCE

1. **Two concepts conflated/absent (P0):** `urgency_score: float = 75.0` on `AidRequest` (models.py:73) is dead — never computed, never used. Humanitarian priority exists only as the enum; execution order exists only implicitly in `assignments[].request_ids`.
2. **UI queue ≠ solver output (P0, reproduced):** `renderSidebar` (`app.js:576`) renders `requests.slice(0,45)` in insertion order (REQ-001…), interleaving LOW/MEDIUM before CRITICAL requests that the plan scheduled first. The plan's first 10 are all CRITICAL; the UI's first 10 include HIGH/LOW/MEDIUM.
3. **Sort key oddity:** `optimizer.py:88` sorts `(priority_weight, -created_at)` descending — correct FIFO-within-priority, but the double negative is fragile and undocumented.
4. **Greedy marginal-distance insertion** (`optimizer.py:96-127`) picks the vehicle minimizing added distance only; ties broken by vehicle iteration order (VEH-01 first) — undocumented, deterministic but arbitrary. Capacity/inventory checks are correct per-vehicle/per-depot.
5. **No deadline feasibility:** `deadline_hours` never consulted; a request with a 2-hour deadline can be scheduled 8 hours out. `estimated_duration_min` is computed but never validated against deadlines.
6. **Unmet demand reasons not classified:** `unmet_request_ids` mixes "inside hazard zone", "no capacity", "no stock" — the UI cannot explain WHY a request is blocked (Part 6 rule 8-9 violated).
7. **Route distance objective:** insertion adds legs greedily; return-to-depot computed afterwards. No route improvement pass — docstring's 2-opt claim is false (see A2).
8. **`total_fulfilled` counts requests, not demand coverage** — labeled "fulfilled" in UI as "Missions Fulfilled". Consistent, but no item-level fill rate exists anywhere.

## SPECIALIST AUDIT C — AGENTIC ACTION & TEST ENGINEERING

**Agent-action → test matrix (pre-repair): every cell is UNTESTED.** No test files exist. Catalog of registered actions:

| Action | Executor | Side effects | Test (pre-repair) |
|---|---|---|---|
| Triage message → AidRequest | `NeedToMissionAgent.triage_message` (agents.py:31) | Writes request into registry (via API) | NONE |
| Assess disruption impact | `RecoveryAgent.assess_impact` (agents.py:80) | Mutates `disruption.affected_missions` | NONE |
| Formulate plan | direct `optimizer.solve_allocation` call (state_engine.py:177) | Creates plan version | NONE |
| Approve replan | `state_engine.approve_replan` (state_engine.py:371) | **Mutates 200+ request statuses, 10 vehicle routes** | NONE |
| Confirm delivery | `state_engine.confirm_delivery` (state_engine.py:395) | Mutates request + depot stock | NONE |
| Transition mission | `main.py:/missions/transition` | Mutates request status unvalidated | NONE |

Additional contract gaps:
- **Agent 1 fabricates data:** if no quantities are detected it invents a default 50 L water + 20 MRE package (agents.py:57-61) — violates its own documented rule "Never invent quantities not in the source" (docs/agent-design.md prompt).
- **Agent 1 has no duplicate detection** despite `duplicate_of_id` field and docstring.
- **No prompt-injection defense:** raw beneficiary text is stored verbatim into `special_notes` and rendered — combined with D9 XSS this is a live injection path.
- **No agent can produce evidence-linked success:** no action returns required evidence; "success" is `{"success": true}` with no postcondition verification.
- **Agent 2 does not exist** (A4): its documented tool contract (GetInventory, InvokeOptimizer...) is unimplemented.

## SPECIALIST AUDIT D — METRICS, DATA & BENCHMARK

| Metric shown | Claimed meaning | Actual formula | Verdict |
|---|---|---|---|
| "Critical Need Fulfillment" KPI | fulfillment of critical needs | `(delivered+dispatched critical)/critical total` — counts undelivered as fulfilled | **WRONG** (shows 100% with 15/200 delivered) |
| "Total Verified Demands" | verified requests | `len(all requests)` incl. REQUESTED/UNDER_REVIEW | **MISLABELED** |
| "Vehicles in Transit" KPI | — | count DISPATCHED requests (not vehicles!) shown under a vehicle label | **MISLABELED** |
| "100% cryptographically signed" | deliveries signed | 15 pre-seeded deliveries have NO signature; only volunteer confirmations produce signatures | **FALSE** |
| "Missions Fulfilled / 200" (benchmark cards) | simulation output | hardcoded 176/118/89 | **FABRICATED** |
| "Replan Latency 0.28 s" | measured | constant | **FABRICATED** |
| "hazard_bypass_pct: 100.0" (replan_delta) | computed | constant | **FABRICATED** |
| "174→171 missions" diff table (index.html) | plan diff | hardcoded HTML | **FABRICATED** |
| "Precision: 98.4%", "12 sensors online", "OR-Tools/Scipy CONNECTED" | — | invented copy | **FABRICATED** |
| Ledger "Timestamp (UTC)" | UTC | `toLocaleTimeString()` local time | **MISLABELED** |
| Carbon kg | computed | `km * 0.21` applied to fabricated km | **UNVERIFIABLE** |
| `unmet_count` in stats | unmet demand | total − delivered − dispatched (includes unverified backlog) | **MISLEADING** |
| "disruption_resilience_score" | — | no formula at all; constants | **UNDEFINED METRIC** |

Denominator errors: `critical_fulfillment_rate` denominator `max(critical_total,1)` silently returns 0-count as 0%. Sample sizes: benchmark "200 requests" never simulated.

## SPECIALIST AUDIT E — PRODUCT TASTE, UX, CLOUD SECURITY

**UX (NGO coordinator):** The mission queue shows insertion order, so the coordinator's mental model of "what happens next" is wrong (B2). No blocked/unresolved section exists — unmet requests are invisible (there is no list of `unmet_request_ids` in the UI at all). The approval banner's diff table is static fiction, so the coordinator cannot make a real decision from real numbers. No way to see WHY a request is unassigned.

**UX (volunteer):** The Field Volunteer console hardcodes "Marcus Vance (Vehicle VEH-02)"; mission select is capped at 25 dispatched entries; volunteer assignment does not exist in data (D6). Signature pad is decorative — signature is discarded; a fixed string "DigitallyVerifiedTouchCapture" is sent.

**Accessibility:** emoji-only icons without `aria-label`s on interactive elements; map interactions are click-only (no keyboard); inspector cards lack focus management; contrast unverified; `alert()` used for critical feedback (blocking, screen-reader unfriendly).

**Trust/taste:** "LIVE NETWORK" pulsing badge in a fully client-fabricated fallback mode is the single most trust-destroying element. Decorative neon glow, gradients, and "OPTIMAL" badge on a greedy heuristic.

**Cloud/security posture:** No auth of any kind (fine for a local demo, must be documented); CORS `*`+credentials (A15); stored XSS (D9); no tenant/organization model despite `docs/security-model.md` describing RBAC — none implemented; no OutSystems deployment exists though README/competition docs claim ODC as the platform.

---

## PART 3 — HIDDEN PROBLEM STATEMENTS (ranked)

**H1 (P0) — Queue/optimizer contradiction.** The solver says CRITICAL-first; the UI queue says insertion order. Evidence: reproduced D1. User impact: coordinator prioritizes the wrong missions. Root cause: UI never projects plan output. Fix: plan-derived dispatch queue + consistency test. Regression test: `test_queue_concordance`.

**H2 (P0) — Success theater.** Benchmark success while nothing was measured (D8); "100% critical fulfillment" while 15/200 delivered (D3); auto-approved v1.0 (D14); fabricated agent telemetry (D17). User impact: judges/coordinators believe false system health. Fix: all metrics computed from state; fabricated copy removed; benchmark runs real scenarios.

**H3 (P0) — Idempotency/execution contradictions.** Duplicate delivery confirmation corrupts inventory (D2); arbitrary transitions corrupt state (D7); second disruption overwrites pending plan (D13); waypoint arrival delivery bypasses audit (A10). User impact: double-dispatch risk, unauditable operations. Fix: state machine + idempotent receipts + versioned plans.

**H4 (P1) — Supply shortage mistaken for ineligibility.** `unmet_request_ids` mixes "blocked by hazard", "no stock", "no capacity" with no classification, so a stock-out at one depot renders a request permanently invisible even when another depot has stock (single-depot check tied to vehicle's base depot: `optimizer.py` only checks `v.base_depot_id` stock — the engine never considers fulfilling from a different depot). Humanitarian contradiction: lack of supply at Depot A is treated as unmet demand though Depot B has inventory. Fix: unmet-reason classification; cross-depot feasibility reporting.

**H5 (P1) — Deadline blindness.** CRITICAL request with 4-hour deadline scheduled last on a 10-stop route; no on-time metric; no deadline feasibility check (D16). Fix: schedule feasibility check + on-time delivery metric.

**H6 (P1) — Evidence gap.** "Proof-of-delivery" exists but signature is a fixed string; pre-seeded deliveries are called "100% cryptographically signed". Fix: honest labeling; signature pad content hashed into receipt (if drawn), else explicit "simulated".

**H7 (P1) — Recovery radius contradiction.** Disruption model carries `hazard_radius_km` but recovery + replanning use different hardcoded radii (3.5 both places, but if the field ever varies, Agent 3's assessment and the optimizer's blocked zones disagree). Fix: single source (D12).

**H8 (P2) — Fabricated fallback universe.** Disconnected frontend simulates deliveries and writes fake audit hashes (A14) — a benchmark or screenshot taken there is indistinguishable from real operation. Fix: explicit SIMULATED banner, no fake hashes.

**H9 (P2) — Volunteer assignment fiction.** Volunteers listed but never assigned; qualification matching (Paramedic for trauma missions) documented but absent. Fix: assign volunteers on plan application with role-aware matching.

**H10 (P2) — Accessibility debt.** See Audit E. Fix: aria labels, keyboard access to inspector, non-blocking toasts.
