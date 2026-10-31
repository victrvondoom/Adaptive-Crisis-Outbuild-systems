# Five-Minute Demonstration Runbook (Phase IV)

Deterministic, replayable, synthetic. Every state comes from actual code
execution. One-click reset. No real messages, no real beneficiary contact,
no invented metrics.

## Setup (one command each)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000   # APP_ENV=development DEV_AUTH_ENABLED=1
# open http://127.0.0.1:8000/ and log in as the coordinator identity
```

One-click reset: **"Disaster Twin" tab → Reset Scenario** (deterministic
seed 42: 200 requests, 3 depots, 10 vehicles, 12 volunteers — the flagship
scenario of the mission brief).

## The five-minute script

| Time | Action | What the audience sees (real execution) |
|---|---|---|
| 00:00 | Mission Command tab | Live operational picture; queue = approved plan projection; blocked requests with explicit reasons |
| 00:30 | NGO Workflows tab → fill intake | Structured request created WITH consent; work order id + duplicate policy visible |
| 01:00 | AI Intake & Triage tab → preset "Emergency Trauma" | Agent 1 extracts items with source-phrase evidence; injection attempts flagged, never obeyed |
| 01:30 | Disaster Twin tab → inject Depot Outage | Recovery plan computed (< 2 ms), PENDING — nothing changes without a human |
| 02:00 | Approve the replan | Plan version increments; completed deliveries preserved; queue concordance 1.0 |
| 02:30 | Field Volunteer tab → select dispatched mission → draw signature → Confirm | Proof-of-delivery receipt persisted; inventory deducted exactly once (idempotent re-confirm shows duplicate) |
| 03:00 | NGO Workflows tab → Propose Transfer to ORG-HIGHLAND | Cross-NGO sharing with sequential dual approval (approve via API as each org) |
| 03:30 | Procurement history + budget check (API) | Budget exceeded → 409; raised → approval → goods receipt → stock increases once |
| 04:00 | NGO Workflows → Generate Report | Impact report: receipts, fulfillment formula, critical coverage, audit chain ✓, provenance sha256 |
| 04:30 | Evidence Ledger tab | Hash-chained audit of every action above; chain verification result |

## API-driven alternative (for judges who prefer curl)

The complete Mission A–E chains are executable as tests:
`python -m pytest tests/test_mission_a_e2e.py tests/test_mission_b_e2e.py
tests/test_mission_c_e2e.py tests/test_mission_d_e2e.py tests/test_mission_e_e2e.py -v`

## Honesty rules enforced in the demo

- Simulated records are labeled SIMULATION_SEED / SEED_SCENARIO / dev identities.
- No message, NGO partnership or delivery is claimed beyond persisted receipts.
- Rejected consent visibly blocks delivery (revocation demo available).
