# AGENTS.md — AIDNEXUS ONE Project Instructions

AIDNEXUS ONE is an evidence-driven, agentic humanitarian mission-control system (OutSystems Build for the Future 2026 entry). This file is the authoritative instruction set for any engineer or AI agent working in this repository.

## Product purpose

Help NGO coordinators turn unstructured aid requests into feasible, optimizer-planned, human-approved dispatch missions that survive disruptions (flooded depots, blocked routes, vehicle breakdowns) with auditable evidence. The demo runs a deterministic simulated crisis (seed=42, 200 requests, 3 depots, 10 vehicles, 12 volunteers).

## Architecture boundaries (actual, not aspirational)

- `backend/app/main.py` — FastAPI REST API + serves the frontend (single origin).
- `backend/app/state_engine.py` — in-memory operational state, plan versioning, hash-chained audit, simulation tick. NO database (documented limitation).
- `backend/app/optimizer.py` — deterministic priority-weighted greedy insertion + **priority-preserving 2-opt** heuristic. It is a HEURISTIC — never describe it as MIP/OR-Tools/solver-exact.
- `backend/app/agents.py` — three agents with explicit action contracts (see `docs/agents/AGENT_ACTION_CATALOG.md`). No LLM is called; Agent 1 is a deterministic classifier/extractor. Never claim model-backed behavior that does not exist.
- `backend/app/benchmark.py` — real simulated comparison of 4 strategies. All numbers computed from execution traces. **Never hardcode benchmark results.**
- `frontend/` — vanilla JS SPA. It renders backend projections only.

## The single most important rule: optimizer–queue alignment (P0)

The active approved `MissionPlanVersion` is the ONLY source of execution order.
- Humanitarian priority = `urgency_score` under `POLICY_VERSION` (models.py).
- Execution order = `scheduled_sequence` from the optimizer.
- `state_engine.get_dispatch_queue()` is a pure projection of the active plan; the frontend renders it verbatim and must never re-sort or recompute priority.
- Blocked requests MUST be visible with an explicit `FeasibilityStatus` reason — never hidden.
- Any change that breaks this is a P0 regression; `tests/test_queue_concordance.py` must stay green.

## Commands

```bash
cd backend
pip install -r requirements.txt
python -m pytest                          # full test suite (fast, <5s)
python -m uvicorn app.main:app --port 8000  # run the app → http://127.0.0.1:8000/
python -m app.benchmark                   # run + store benchmark artifacts
```

## Coding standards

- Python 3.12, Pydantic v2 (`model_dump`, not `.dict`). Type hints required in backend.
- Deterministic everywhere: any randomness must come from an explicit seeded `random.Random`.
- No new dependencies without justification. Frontend stays dependency-free (no CDN, no npm).
- Match existing style; smallest coherent change; no speculative abstractions.

## Testing requirements

- Every agent action contract has tests (`tests/test_agents.py`); a new agent action without tests is incomplete.
- A behavior change ships with a regression test that fails without the fix.
- Never weaken an assertion to make a test pass. Never mock production code paths.
- Metric changes must update `docs/metrics/METRIC_REGISTRY.md` and `tests/test_metrics.py`.

## Data & metric truth rules

- Every displayed number must trace to a registered metric (`docs/metrics/METRIC_REGISTRY.md`) with formula, numerator, denominator, and source.
- "Fulfilled" means DELIVERED (with receipt). Dispatched ≠ fulfilled.
- Never fabricate, estimate, or "demo-fill" a metric. If it cannot be measured, show NOT MEASURED.
- Benchmark results must record seed, size, and integrity metrics; report regressions honestly.

## Agentic action rules

- Agents advise; humans approve. No agent may activate a plan, deny assistance, or invent quantities/items.
- Agent 1 output is a DRAFT with evidence (`source_text` per item); unparsed messages → human review, never invented defaults.
- Agent 3 impact assessment uses `disruption.hazard_radius_km` (never a hardcoded radius).
- Every consequential action logs a hash-chained audit event with actor, entity, and details.
- Delivery confirmation is idempotent; completed deliveries are immutable.

## Security requirements

- This is a single-tenant local demo: NO auth, in-memory state. Say so; don't imply otherwise.
- Escape all dynamic strings in the frontend (`escapeHtml`); sanitize free text on input.
- Never read or commit real secrets; `.env.example` holds placeholders only.
- No production deployments from this repo without explicit human authorization.

## Definition of done

A feature is COMPLETE only when: executed, observed via tests, documented in the
relevant registry, and its metrics (if any) are computed from real data.
Code existing, a prompt written, or an agent returning success text is NOT completion.

## Deployment restrictions

Local demo only. No cloud deploys, no OutSystems publishing, no external API calls without credentials and explicit authorization.

## How to update project context

- Current implementation state: `docs/context/CURRENT_STATE.md` (update before ending a session).
- Session log: `docs/context/WORKLOG.md`.
- Architecture decisions: `docs/context/DECISION_LOG.md`.
- System invariants: `docs/context/SYSTEM_INVARIANTS.md`.
- Implementation-status labels: IMPLEMENTED / PARTIALLY_IMPLEMENTED / DOCUMENTED_ONLY / MOCKED / SIMULATED / NOT_IMPLEMENTED / BLOCKED — use them; never present a planned feature as implemented.
