# AIDNEXUS ONE — Adaptive Crisis Outbuild Systems

> **The Self-Healing Humanitarian Network.** Evidence-driven, agentic mission control for humanitarian relief dispatches. OutSystems Build for the Future Hackathon 2026 entry.

## What this actually is (implementation status, honestly stated)

A **local, self-contained demo application**: a FastAPI backend (Python) that
plans, simulates and audits humanitarian dispatch missions, serving a vanilla
JS mission-control dashboard. It runs a deterministic crisis scenario
(seed=42: 200 aid requests, 3 depots, 10 vehicles, 12 volunteers) in memory.

| Capability | Status |
|---|---|
| Optimization-based dispatch planning (priority insertion + priority-preserving 2-opt) | ✅ Implemented (heuristic — not MIP/OR-Tools) |
| Humanitarian priority policy with versioned plan data contract | ✅ Implemented |
| Plan-derived dispatch queue (optimizer output is the only execution order) | ✅ Implemented, concordance-tested |
| Disruption recovery (depot outage, hazard zones, vehicle breakdown) with human approval gate | ✅ Implemented |
| 3 agents with tested action contracts (triage / planning / recovery) | ✅ Implemented (deterministic; no LLM) |
| Idempotent proof-of-delivery, state-machine-validated transitions, hash-chained audit | ✅ Implemented |
| Real 4-strategy benchmark simulation with integrity metrics | ✅ Implemented |
| 81-test automated suite | ✅ Implemented |
| LLM integration (Bedrock/Azure), OutSystems ODC app, Twilio SMS, auth/multi-tenancy, DB persistence | ❌ Not implemented (spec-only; see `docs/context/CURRENT_STATE.md`) |

## Quick start

```bash
cd backend
pip install -r requirements.txt

# Run the tests (81 tests, ~3 s)
python -m pytest

# Run the app
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000/
```

Windows 1-click: run `start.bat` (repo root's parent folder) or `start.ps1`.

## Run the benchmark

```bash
cd backend
python -m app.benchmark        # runs 9-run matrix, writes JSON artifacts to benchmarks/results/
```
Or in the app: **Benchmark Arena → Run** (live simulation via API).
Results are computed from real execution traces — they vary by seed and are reproducible.

## Project structure (actual)

```
aidnexus-one/
  AGENTS.md                      # authoritative project instructions
  backend/
    app/                         # FastAPI app: models, optimizer, agents, state engine, benchmark, API
    tests/                       # 81 tests: optimizer, state machine, queue concordance, agents, metrics, API
    requirements.txt, pytest.ini
  frontend/                      # vanilla JS/CSS/HTML mission-control dashboard (no build step, no CDN)
  benchmarks/results/            # committed benchmark artifacts (JSON)
  docs/
    audit/                       # initial state, ranked findings, bugs fixed, unresolved issues, final report
    context/                     # current state, invariants, decision log, worklog
    metrics/                     # metric registry, verified metrics
    agents/                      # agent action catalog, agent evaluation report
    benchmarks/                  # final benchmark report
    quality/                     # security review, UX review
    (plus the original planning/spec documents, clearly aspirational where not implemented)
  ../outsystems/                 # ODC application blueprints (spec only — no ODC app is built)
```

## Core differentiator

**Autonomous humanitarian disruption recovery with evidence.** When a depot
floods or a route is severed, Agent 3 assesses impact, completed deliveries are
sealed as immutable, Agent 2 replans around the disruption in milliseconds, and
**nothing changes until a human approves** — with a real before/after diff and a
hash-chained audit trail. Benchmark: replanning recovers 44% of
disruption-affected deliveries (baselines recover 0%) and delivers +10–18% more
missions than static optimization (`docs/benchmarks/FINAL_BENCHMARK_REPORT.md`).

## Honesty statement

This README describes the implemented system only. aspirational/planned
capabilities are marked ❌ and detailed in `docs/context/CURRENT_STATE.md`.
The benchmark numbers above come from the committed artifacts in
`benchmarks/results/` and can be regenerated in ~1 second.

## License

MIT — see [LICENSE](./LICENSE).
