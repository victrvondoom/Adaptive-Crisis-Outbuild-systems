# UNRESOLVED ISSUES — AIDNEXUS ONE

Honest list of what is NOT fixed and why. No P0 items remain open.

## Blocked on external access/credentials

| # | Item | Blocker | What exists instead |
|---|---|---|---|
| U1 | LLM-backed Agent 1 (Bedrock/Azure) + real-model evaluation suite | No cloud credentials | Deterministic triage with full contract tests; spec in `docs/agent-design.md`; provider-interface slot documented |
| U2 | OutSystems ODC application (screens, server actions, entities) | No ODC environment | Complete spec set in `../../outsystems/*.md`; REST surface in `main.py` matches `integration-contracts.md` |
| U3 | Twilio SMS volunteer notifications | No Twilio account | `.env.example` placeholder only; never claimed in UI |
| U4 | OR-Tools/MIP solver upgrade | Unnecessary at demo scale + offline constraint | Honest heuristic, benchmarked; decision DL-2 |
| U5 | Production deployment of any kind | Explicit authorization required (none given) | Local demo only; deployment docs marked as design |

## Accepted limitations (documented, by design for a hackathon demo)

| # | Item | Why accepted | Mitigation |
|---|---|---|---|
| U6 | No authentication/RBAC/multi-tenancy | Local single-tenant demo | SECURITY_REVIEW R1/R2 with production path |
| U7 | In-memory persistence (state lost on restart) | Demo scope | Documented; receipts/audit ephemeral; DB is the first production step |
| U8 | Audit retention cap 5000 (in-memory) | Memory bounds | Chain intact within retention; UI states retention honestly |
| U9 | Client renders top-60 queue entries | Payload/UX density | Explicit "+N more" marker; full data in API |
| U10 | Map is click-only (no keyboard map interaction); no formal WCAG audit | Time-boxed pass | Focus rings, aria labels added; formal a11y audit open |

## Known product-behavior caveats (honest, not defects)

| # | Cave | Detail |
|---|---|---|
| U11 | FIFO can out-fulfill AIDNEXUS on raw count at high scarcity | Real trade-off documented in FINAL_BENCHMARK_REPORT finding 2: FIFO abandons critical coverage (41% vs 63%) at 3.1× distance. A fairness/coverage-aware objective could weight this; current policy prioritizes critical coverage by design |
| U12 | One benchmark regression vs greedy distance (seed 123, n=100, −5.3%) | Recovery from mid-route positions can lengthen routes; reported openly |
| U13 | Deterministic Agent 1 misses cues outside its lists | Defaults to human review rather than guessing (safe direction) |

## Highest-priority next actions

1. Add CI (GitHub Actions) running `pip install -r requirements.txt && pytest` + benchmark smoke — the quality gates are defined but not wired to a CI provider (no repo remote exists).
2. Persistence layer (SQLite) behind the engine interface.
3. Auth + roles if the demo will ever face a second user.
4. Model-backed Agent 1 behind a provider interface + real-model eval harness when credentials arrive.
