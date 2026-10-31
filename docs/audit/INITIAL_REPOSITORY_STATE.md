# INITIAL REPOSITORY STATE — AIDNEXUS ONE

**Audit date:** 2026-10-31 · **Auditor:** Mistral Vibe (Principal Architect / Staff Engineer role)
**Baseline commit:** `e30669a` — "Baseline capture: AIDNEXUS ONE as received, pre-audit" (git initialized in `aidnexus-one/`; the outer folder had **no git repository**).

---

## 1. Repository Identity

| Item | Actual value |
|---|---|
| Project name | AIDNEXUS ONE — "The Self-Healing Humanitarian Network" |
| Location | `C:\Users\Administrator\Downloads\Adaptive Crisis Outbuild systems\aidnexus-one` (plus sibling `outsystems/` spec folder and `start.bat`/`start.ps1` launchers one level up) |
| Git state at receipt | **Not a git repository** — no history, no branch, no remotes, no stashes. Git initialized by auditor to capture the baseline. |
| Active branch | `main` (new, contains only the baseline commit) |
| Remotes | None |
| Modified/untracked files | None at receipt (no prior VCS) |
| Competition | OutSystems Build for the Future Hackathon 2026 |

## 2. What Actually Exists (Implementation Authority)

### Runtimes and frameworks (VERIFIED EXECUTING)
- **Backend:** Python 3.12.10, FastAPI 0.115.6, Pydantic 2.10.4. Entrypoint: `backend/app/main.py` (`uvicorn app.main:app`, port 8000). Boots and serves REST API + static frontend. VERIFIED via TestClient.
- **Frontend:** Vanilla HTML/CSS/JS single page (`frontend/index.html`, `js/app.js` 1122 lines, `css/style.css`). Served by the same FastAPI app at `/`.
- **Data store:** In-memory only (`CrisseStateEngine`/`CrisisStateEngine` singleton). No database, no persistence. All state lost on restart.
- **External APIs/integrations:** **NONE implemented.** No OutSystems ODC, no AWS Bedrock, no Azure AI, no Twilio, no OR-Tools, no LLM of any kind. `.env.example` lists them but no code reads these variables.
- **Agent framework:** Three hand-written Python classes/roles in `backend/app/agents.py` + `state_engine.py`. **No LLM, no tool registry, no schema-validated model output.** Agent 2 (Resource Strategist) **has no class at all** — it exists only as an audit-log actor string `AGENT-02-RESOURCE` wrapping a direct optimizer call.
- **Optimization algorithm:** `backend/app/optimizer.py` — priority-weighted greedy insertion heuristic (pure Python, haversine distances). **Not** OR-Tools, **not** MIP, **no 2-opt despite its docstring claiming "local 2-opt route improvement". Priority weights: CRITICAL=1000, HIGH=300, MEDIUM=80, LOW=20.
- **Benchmarks:** `backend/app/benchmark.py` — **entirely hardcoded constants** (fulfilled 176/118/89, km 412.4/589.6/894.2, etc.). No simulation occurs. `rng = random.Random(seed)` is created and never used.
- **Tests:** **ZERO.** No test files, no `requirements.txt`, no CI config, no lint/type-check config anywhere.
- **Deployment:** None. `start.bat`/`start.ps1` launch a local uvicorn dev server with `--reload`.

### Entry points
1. `start.bat` / `start.ps1` (repo root's parent) → `uvicorn app.main:app` + open browser.
2. `backend/app/main.py` — FastAPI app: `/api/v1/{health,state,sim/tick,sim/control,scenario/reset,disrupt,replan/approve,nlp/triage,triage,deliveries/confirm,benchmark/run,missions/transition}` + static mounts.
3. `frontend/index.html` — SPA with 6 tabs (Mission Command, Disaster Twin, AI Intake, Field Volunteer, Benchmark Arena, Evidence Ledger).

### Documentation inventory (16 docs + 4 ADRs + 5 OutSystems spec files)
Extensive aspirational documentation. Key gap: docs describe ODC screens, server actions, data entities, OR-Tools solver, Bedrock LLM agents, Twilio SMS — **none of which exist in code**. `docs/benchmark-methodology.md` explicitly forbids hardcoded results ("Anti-Fabrication Controls") — the implementation violates every one of those controls.

---

## 3. Baseline Defects REPRODUCED (hard evidence, run on the received code)

Reproduction script output (2026-10-31, Python 3.12.10, working tree at `e30669a`):

| # | Defect | Evidence (reproduced) | Severity |
|---|---|---|---|
| D1 | **UI dispatch queue is NOT derived from the optimizer plan.** `renderSidebar` uses `state.requests.slice(0,45)` in insertion order. | Plan's first 10 requests: all `CRITICAL`. UI queue's first 10: `[CRITICAL, HIGH, CRITICAL, HIGH, LOW, MEDIUM, ...]`. Orders disagree. | **P0** |
| D2 | **Delivery confirmation is not idempotent → duplicate inventory deduction.** | Depot water stock `12000.0 → 11628.0` (1st confirm) `→ 11256.0` (duplicate confirm). | **P0** |
| D3 | **`critical_fulfillment_rate` counts DISPATCHED (undelivered) as fulfilled.** | Dashboard shows **100.0%** critical fulfillment while only 15/200 requests delivered. | **P0 (measurement)** |
| D4 | **`preserve_request_ids` ignored by optimizer while its explanation claims "Preserved 1 existing delivery commitments".** | Parameter unused in `solve_allocation`; explanation text fabricates preservation. | **P0 (integrity)** |
| D5 | **`/api/v1/state` silently truncates 200 → 140 requests.** | `len(engine.requests)=200`, API returns 140. Requests 141–200 invisible to the UI. | **P1** |
| D6 | **Volunteers are never assigned.** `assigned_volunteer_id` never set by any code path. | 12 volunteers, 0 assigned. Field Volunteer tab is a prop. | **P1** |
| D7 | **`/api/v1/missions/transition` accepts ANY transition with no validation** (e.g. DELIVERED→REQUESTED, or unauthenticated `attacker` marking DELIVERED). | POST returns `success: True` for arbitrary status. | **P0 (state integrity)** |
| D8 | **Benchmark is fabricated.** Identical output for seed 42 and seed 999. | `b1["metrics"] == b2["metrics"] → True`. | **P0 (measurement)** |
| D9 | **Stored XSS** via `innerHTML` rendering of unescaped API data (disruption titles, requester names, audit summaries all flow from POST payloads into `innerHTML`). | `renderCrisisMap` renders `dis.title` raw; `filterAuditLedger` renders `ev.summary` raw. | **P0 (security)** |
| D10 | **Frontend triage calls a doubled URL** `${API_BASE}/api/v1/nlp/triage` = `/api/v1/api/v1/nlp/triage` → **404 always** → silently falls back to a fake local parser. | TestClient: frontend-style URL → 404; correct URL → 200. | **P0 (functional)** |
| D11 | Audit "ledger" is **not chained** and **not immutable** (individual hashes only; events silently dropped past 300; cleared on reset) despite UI claims of "cryptographically chained and immutable". | Source inspection `state_engine.py:log_audit`. | **P1 (trust)** |
| D12 | RecoveryAgent uses **hardcoded 3.5 km hazard radius**, ignoring `disruption.hazard_radius_km`. | `agents.py` L97 vs model field. | **P1** |
| D13 | Plan versioning hardcoded to `"v2.0"`: a second disruption **overwrites the pending plan**; no v3+ possible; `approve_replan` can only approve "v2.0". | `inject_disruption`/`approve_replan` source. | **P0 (reliability)** |
| D14 | Plan v1.0 is **auto-approved** by code (`is_approved=True, approved_by="Lead Mission Coordinator"`) contradicting "Human approval gate: REQUIRED for all plan versions" shown in the UI. | `generate_initial_plan`. | **P1 (trust)** |
| D15 | `advance_simulation` auto-delivers on waypoint arrival **without audit event** and can double-deduct with `confirm_delivery`. | Source `advance_simulation` — deducts depot stock, logs nothing. | **P1 (measurement/audit)** |
| D16 | Optimizer ignores `deadline_hours` entirely (no time-window feasibility) while docstring/model name claim "CVRPPDTW" (deadline time windows). | No reference to `deadline_hours` in `optimizer.py`. | **P1** |
| D17 | Fabricated UI claims: "Urgency NLP Classifier: Precision: 98.4%", "OR-Tools / Scipy: CONNECTED", "12 sensors online", "Double-dispatch prevention lock: ENGAGED", hardcoded plan-diff table "174→171 missions", "100% cryptographically signed". | `index.html` Disaster Twin tab; none backed by code. | **P0 (trust)** |
| D18 | Disconnected "fallback" mode shows the same **"LIVE NETWORK"** badge and fabricated stats (`critical_fulfillment_rate: 96.2`) as if real. | `initFallbackState` + header badge. | **P1 (trust)** |
| D19 | CORS `allow_origins=["*"]` combined with `allow_credentials=True`. | `main.py` middleware. | **P2 (security, demo scope)** |
| D20 | README claims structure (`services/`, `tests/`, `benchmarks/`, `scripts/`, `assets/`) and stack (OR-Tools, ODC, Bedrock, Twilio) that **do not exist**. | `find` output; no requirements.txt. | **P1 (documentation truth)** |

## 4. Baseline Verification Results (before any repair)

- App boots: **PASS** (health endpoint 200).
- Test suite: **DOES NOT EXIST** — 0 tests, 0 %, nothing to pass.
- Benchmark: returns constants regardless of seed — **not a measurement**.
- The received code was NOT modified before this report; all reproductions ran against the pristine tree captured in `e30669a`.

## 5. Authorization Constraints Observed

- No production credentials, `.env` values, keys or tokens were read or printed (only `.env.example`, which contains placeholders).
- No destructive git operations performed; baseline commit is additive.
- No deployments, no external service calls.
