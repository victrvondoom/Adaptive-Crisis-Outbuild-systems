# AGENT EVALUATION REPORT — AIDNEXUS ONE

Evaluation of the three registered agents against the three-level agentic
benchmark model (action / agent / system). Current build: deterministic
agents (no LLM) — evaluation is therefore exact and reproducible; the
model-backed evaluation harness remains specified but NOT_IMPLEMENTED
(no credentials), see AGENT_ACTION_CATALOG.md.

## Level A — Action benchmarks (deterministic, CI)

| Action | Cases | Correct action/schema/evidence | Precondition validation | Escalation correctness | Result |
|---|---|---|---|---|---|
| A1-TRIAGE | 7 (valid, no-quantity, ambiguous, duplicate, injection, empty, spam) | 7/7 schema-valid, evidence attached | rejects nothing silently; empty→review draft | review flags raised exactly when required (4/4) | **PASS** |
| A2-PLAN | 4 (normal, coverage, blocked-reporting, order-fidelity) | 4/4 schema-valid; coverage_complete true | infeasible inputs → blocked-with-reason, never silent drop | approval_request always emitted; never self-approves | **PASS** |
| A3-ASSESS | 2 (radius fidelity, preservation) | 2/2 | delivered missions never affected | replan proposal stays approval-gated | **PASS** |
| SYS-DELIVERY | 3 | idempotent receipts; single deduction | cancelled requests rejected | — | **PASS** |
| SYS-TRANSITION | 6 | illegal transitions rejected with allowed-list | terminal states enforced | — | **PASS** |
| SYS-APPROVE | 4 | only pending plan approvable | double-approval rejected; supersede audited | — | **PASS** |

## Level B — Agent benchmarks

- Task success (postconditions hold): **100%** across the deterministic suite (81 tests).
- Goal completion without invented data: verified (A1 evidence fields; no-quantity case).
- Unnecessary tool calls: n/a (deterministic tool graph, no LLM).
- Human escalation correctness: duplicates/unparsed/injection/CRITICAL → human review (tested).
- Human override rate: 1 required approval per plan version (by design); v1.0 bootstrap auto-approval is labeled and audited.
- Cost per task / latency: 0 marginal cost; planning P95 ≈ 9 ms @ 500 requests; replan ≈ 1–2 ms.

## Level C — System benchmarks

From `docs/benchmarks/FINAL_BENCHMARK_REPORT.md` (10 runs, real simulation):
- Complete mission success: AIDNEXUS delivers +10% mean (up to +17.8%) vs static-opt; dominates at n=500.
- Replanning quality: 44.4% of disruption-affected deliveries recovered (baselines: 0%).
- Duplicate side effects: 0 across all runs (verified during execution).
- Audit completeness: every consequential action logs a chained event (tested).
- Service resilience: recovery plans computed in ~1–2 ms; approval-gated before any state change.

## Adversarial / negative results

| Case | Outcome |
|---|---|
| Prompt injection in beneficiary text | sanitized + flagged; stored text clean (tested) |
| Duplicate intake | flagged `duplicate_of_id`, human review; never auto-denied |
| Unparseable message | empty item list + review flag; NOTHING invented (old build fabricated 50 L + 20 MRE — FIXED) |
| Illegal state transition (incl. attacker setting DELIVERED) | 400 with allowed-transition list |
| Duplicate delivery confirmation | idempotent receipt; inventory deducted once |
| Second disruption while plan pending | pending plan superseded with audit, not overwritten |
| Disruption with no affected missions | assessment handles empty sets |
| Cancelled request delivery attempt | rejected |

## Honest limitations

- No real-model evaluation: precision/latency/cost of an LLM-backed Agent 1 are
  NOT MEASURED (the pre-repair build claimed "98.4% precision" with no basis — removed).
- Deterministic triage is rule-based; it will miss urgency cues not in its cue
  lists. Mitigation: default-to-review escalation paths, human verification gate.
