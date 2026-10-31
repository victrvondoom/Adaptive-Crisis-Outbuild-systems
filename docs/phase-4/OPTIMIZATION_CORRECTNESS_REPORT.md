# Optimization and Queue Correctness Report (Phase IV)

The optimizer is a core preserved asset. No algorithm was replaced in Phase IV.

## What runs (`backend/app/optimizer.py`)

Priority-weighted greedy insertion + **priority-preserving 2-opt** — a
deterministic HEURISTIC. It is never described as MIP, OR-Tools, or exact.

## Correctness properties — all TESTED, unchanged in Phase IV

| Property | Test |
|---|---|
| Dispatch queue is a pure projection of the approved active plan | `tests/test_queue_concordance.py` (concordance 1.0) |
| Execution order = `scheduled_sequence`; humanitarian priority = `urgency_score` under `POLICY_VERSION` — never conflated | queue concordance + optimizer tests |
| Blocked requests visible with explicit `FeasibilityStatus` + explanation | `tests/test_mission_b_e2e.py` |
| Completed deliveries are immutable across replans | `tests/test_mission_b_e2e.py` (preservation assertions) |
| Commitment preservation (in-flight assignments kept unless affected) | `tests/test_mission_b_e2e.py::test_recovery_preserves_unaffected_commitments` |
| Small-instance exactness comparison | `tests/test_optimizer_proofs.py` |
| Priority policy regression (critical > high > medium) | `tests/test_optimizer.py` |
| Inventory infeasibility never produces phantom assignments | optimizer + queue tests |
| Phase IV additions: API-intake requests enter the same authoritative engine; replans include them; version sequence increments only through the sanctioned replan path | `tests/test_mission_a_e2e.py`, `test_mission_b_e2e.py` |

## Honest claims

- Optimality: NOT claimed globally; the 2-opt pass preserves priority ordering while improving distance. Optimality-gap measurement remains PROPOSED (atlas OR-10 domain).
- Phase IV did not modify the optimizer or the plan contract; all Phase I–III optimizer proofs remain green (verified: full suite 222 passed).
