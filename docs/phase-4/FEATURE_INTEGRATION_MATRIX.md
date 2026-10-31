# Feature Integration Matrix (Phase IV)

Atlas: 1,093 records — EXISTING_VERIFIED=285, IMPLEMENTED_TESTED=5, PARTIALLY_IMPLEMENTED=6, BLOCKED_EXTERNAL_DEPENDENCY=3, PROPOSED=781, REJECTED=13.

## Phase IV implementation scope (waves 3–6) — atlas capability areas mapped to code

| Wave | Capability | Atlas domain area | Code owner | Automated test |
|---|---|---|---|---|
| 3 | API intake with consent + dedup (Mission A front door) | INT intake, BEN consent | `main.py` POST /requests + `persistence_phase4.py` | `tests/test_mission_a_e2e.py` |
| 3 | Request→plan→approval→delivery→receipt chain | DSP dispatch, APP approvals | `state_engine` (existing) | `tests/test_mission_a_e2e.py` |
| 4 | Cross-NGO resource transfer (Mission C) | ORG collaboration, INV shared stock | `persistence_phase4.py` + /transfers API | `tests/test_mission_c_e2e.py` |
| 5 | Procurement-to-inventory (Mission D) | PRO procurement, INV replenishment | `persistence_phase4.py` + /procurements API | `tests/test_mission_d_e2e.py` |
| 6 | Self-healing recovery E2E (Mission B) | REC recovery | `state_engine.inject_disruption` (existing) | `tests/test_mission_b_e2e.py` |
| 6 | Impact & accountability report (Mission E) | IMP impact, EVD evidence | `/impact/report` | `tests/test_mission_e_e2e.py` |
| 9 | Outbox consumer (event-driven reliability) | SRE resilience | `/outbox/dispatch` | `tests/test_mission_events.py` |

## Implemented but not surfaced in UI (gap register, honestly labeled)

- Inventory expiry / certification expiry / case notes / delegations: API + tests exist; no dedicated UI panels (API-only access).
- Agent runtime executions: persisted and DB-queryable; no UI panel.
- These are IMPLEMENTED + TESTED at the API level, NOT claimed as complete user-facing features.

## Documented but not implemented (honest, remains PROPOSED/BLOCKED)

- All 781 PROPOSED atlas records remain specifications.
- ODC native app: BLOCKED (no credentials in this environment).
- LLM real inference: adapter ready, BLOCKED (no keys).
