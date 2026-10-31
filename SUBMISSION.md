# SUBMISSION PACKAGE — AIDNEXUS ONE

**Entry**: OutSystems "Build for the Future" Hackathon 2026
**Repo**: https://github.com/victrvondoom/Adaptive-Crisis-Outbuild-systems (branch `main`)
**Verified at submission**: 256 backend tests + 11 real-browser journeys, all green, proven from a clean clone.

## One-paragraph summary

AIDNEXUS ONE is an evidence-driven humanitarian operations platform: it turns
unstructured distress messages into optimizer-planned, human-approved dispatch
missions across multiple NGOs, survives disasters mid-operation with
self-healing replanning that never loses completed work, and produces
auditable, provenance-hashed impact reports from real delivery evidence.
Every consequential action is permission-guarded, tenant-isolated, idempotent
and hash-chain audited — and every engineering claim in this package is
backed by an executable test in the repository.

## Feature → evidence map (judges: run any of these)

| Claim | How to verify | Time |
|---|---|---|
| 256-test suite passes | `cd backend && python -m pytest` | ~60 s |
| Real browser journeys (login, triage, disruption approval, signature delivery, tenant isolation, studio) | `python -m pytest tests/browser -m browser` | ~40 s |
| Self-healing recovery preserves completed deliveries, queue = approved plan | `python -m pytest tests/test_mission_b_e2e.py -v` | ~5 s |
| Cross-NGO transfer with dual approval + atomic dual-org ledger | `python -m pytest tests/test_mission_c_e2e.py -v` | ~5 s |
| Consent required at intake; revoked consent blocks delivery (409) | `tests/test_mission_a_e2e.py` | ~5 s |
| Idempotent delivery + replay-safe ledger (DB unique keys) | `tests/test_phase4_security.py -v` | ~10 s |
| Rate limiting 429 + Retry-After, tenant-isolated budgets | `tests/test_rate_limiter.py -v` | ~5 s |
| Reproducible optimizer benchmarks (incl. honest losses) | `cd backend && python -m app.benchmark` | ~2 min |
| 1,080-feature portfolio with programmatic validator | `python scripts/validate_feature_atlas.py` | ~10 s |

## The 5-minute demo (live, deterministic, one-click reset)

Follow `docs/phase-4/DEMO_RUNBOOK.md`:
00:00 Mission Command → 00:30 NGO Workflows intake (consent) → 01:00 AI Triage
→ 01:30 Disaster Twin: depot failure → 02:00 human-approved recovery plan →
02:30 Field Volunteer signature delivery (idempotent receipt) → 03:00
cross-NGO transfer (dual approval) → 04:00 impact report with provenance
hash + audit chain ✓ → 04:30 Evidence Ledger. Screenshots in
`docs/phase-2/screenshots/`.

## Architecture in one diagram

`docs/system-design/ARCHITECTURE_OVERVIEW.md` — and the in-app **System
Design Studio** tab walks all 20 foundational system-design topics mapped to
this codebase with honest status chips and a live failure lab.

## What is BLOCKED (no credentials exist; nothing faked)

OutSystems ODC access · live LLM provider keys · OIDC identity provider ·
managed PostgreSQL · notification providers. Adapters/contracts are prepared
and labeled BLOCKED — the platform never simulates a live integration.

## AI-assistance disclosure

Built with Mistral Vibe (AI coding agent) under the direction and ownership
of the repository owner, in line with the competition's AI policy. All
capabilities listed above are demonstrated by tests committed in this
repository — not by documentation claims.
