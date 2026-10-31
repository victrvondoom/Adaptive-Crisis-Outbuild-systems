# Phase IV Test Evidence

All commands run on branch `phase-4-autonomous-operations` at the final Phase IV
commit. Full suite: **222 passed, 9 deselected (browser marker)**; browser suite:
**10/10 green** (run separately with `-m browser`).

## Commands

```bash
cd backend
python -m pytest                      # 222 passed (deterministic CI gate)
python -m pytest tests/browser -m browser   # 10/10 journeys, real Chromium
python -m app.benchmark               # fresh artifact: benchmark_matrix_1793438128.json
```

## New Phase IV test files (39 backend tests)

| File | Tests | Covers |
|---|---|---|
| tests/test_mission_a_e2e.py | 7 | intake (schema/consent/dedup), full chain to verified assistance, consent-revocation blocking, tenant isolation of traces |
| tests/test_mission_b_e2e.py | 2 | 3-disruption self-healing chain, completed-work + commitment preservation, queue concordance, blocked visibility |
| tests/test_mission_c_e2e.py | 6 | cross-NGO transfer: validation, dual approval, dispatch/receive, idempotency, cancellation, tenant isolation |
| tests/test_mission_d_e2e.py | 5 | supplier verification gate, budget enforcement, receipt idempotency, discrepancy handling, isolation, permissions |
| tests/test_mission_e_e2e.py | 5 | impact reports: formula honesty, evidence reconciliation, actual-vs-estimated, provenance, tenant isolation |
| tests/test_mission_events.py | 3 | outbox enqueue + idempotent dispatch, permission gating |
| tests/test_phase4_security.py | 11 | red-team probes (see SECURITY_AND_PRIVACY_REPORT.md) |
| tests/browser/test_journeys.py | +1 journey | NGO Workflows UI: intake with consent, live impact report |

## Preserved regression evidence (unchanged suites, all green in the 222)

- `tests/test_queue_concordance.py` — optimizer/queue alignment (P0 invariant).
- `tests/test_optimizer_proofs.py`, `test_optimizer.py` — optimizer properties.
- `tests/test_persistence_phase2.py` — durability, idempotent receipts, audit chain.
- `tests/test_authz_phase2.py` — tenant isolation, role permissions.
- `tests/test_agents_runtime.py`, `test_agents.py` — agent control plane.
- `tests/test_feature_atlas.py`, `test_feature_atlas_api.py` — atlas gates + API.

## Benchmark evidence

- Fresh Phase IV artifact: `benchmarks/results/benchmark_matrix_1793438128.json`
  (9 runs, seeds 42/123/256 × n 50/100/200; 0 integrity violations; recovery
  latency ≤ 0.002 s). Honest comparison incl. losses in BENCHMARK_COMPARISON.md.
- Committed Phase I artifacts untouched.
