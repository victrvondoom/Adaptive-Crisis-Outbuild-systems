# API Compatibility Matrix (Phase IV)

All endpoints under `/api/v1`, auth = bearer token + `X-Org-Id`, permission enforced via `guard()`.

## Existing (Phase I–III) — contracts unchanged in Phase IV

| Endpoint | Permission | Notes |
|---|---|---|
| GET /state, /dispatch-queue | READ_ORG_DATA | queue is a pure plan projection |
| POST /sim/tick, /sim/control, /scenario/reset | SIM_CONTROL | deterministic seeds |
| POST /disrupt | INJECT_DISRUPTION | recovery planning |
| POST /replan/approve | APPROVE_PLAN | version-bound approvals |
| POST /triage | CREATE_REQUEST | agent action contracts |
| POST /deliveries/confirm | CONFIRM_DELIVERY | idempotent receipt |
| GET /missions/{id}, POST /missions/transition | per action | validated state machine |
| GET /orgs, /audit, /orgs/export | per action | tenant-scoped |
| inventory expiry, certifications, notes, delegations (Phase III v2) | per action | evidence in test_phase3_features.py |
| /features* (atlas) | READ_ORG_DATA / MANAGE_MEMBERS | live portfolio + validator |

## Added in Phase IV (additive only; no existing route changed)

| Endpoint | Permission | Mission |
|---|---|---|
| POST /api/v1/requests | CREATE_REQUEST | A — intake with consent + dedup |
| GET /api/v1/requests/{id} | READ_ORG_DATA | A — work-order trace |
| POST /api/v1/requests/{id}/consent/revoke | CREATE_REQUEST | A — consent withdrawal |
| GET /api/v1/impact/report (?request_id=) | READ_ORG_DATA | E — evidence-linked impact report |
| POST /api/v1/transfers | RUN_OPTIMIZATION | C — propose cross-NGO transfer |
| POST /api/v1/transfers/{id}/approve-source | APPROVE_PLAN | C — source-organization approval |
| POST /api/v1/transfers/{id}/approve-destination | APPROVE_PLAN | C — destination approval |
| POST /api/v1/transfers/{id}/dispatch | APPROVE_PLAN | C — inventory movement, idempotent |
| POST /api/v1/transfers/{id}/receive | CONFIRM_DELIVERY | C — handover confirmation |
| POST /api/v1/transfers/{id}/fail | APPROVE_PLAN | C — failure recovery path |
| GET /api/v1/transfers | READ_ORG_DATA | C — both sides see their own view only |
| GET/POST /api/v1/suppliers | READ_ORG_DATA / MANAGE_MEMBERS | D — supplier registry + verification |
| POST /api/v1/procurements | CREATE_REQUEST | D — proposal |
| POST /api/v1/procurements/{id}/approve | APPROVE_PLAN | D — approval (cost + budget check) |
| POST /api/v1/procurements/{id}/receive | CONFIRM_DELIVERY | D — goods receipt + discrepancy handling |
| GET /api/v1/procurements | READ_ORG_DATA | D |
| POST /api/v1/outbox/dispatch | SIM_CONTROL | 9 — idempotent outbox consumer |

## Schema evolution policy

Additive columns only, nullable, migration-numbered (v3 adds new tables only).
No existing response field removed or renamed in Phase IV. Contract tests:
`tests/test_mission_*_e2e.py` assert request/response shapes.
