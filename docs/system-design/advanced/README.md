# Advanced System Design (Topics 21–40) — AIDNEXUS ONE, Phase VI

Interactive companion: Studio tab → **ADVANCED SYSTEM DESIGN · Topics 21–40**, Failure Lab, Benchmark Lab, Production Engineering, Architecture Map.

**Labels.** REAL MEASURED = executed on a disposable database by the server at click time. SIMULATED = deterministic model of infrastructure we do not run. REAL TELEMETRY = counters from the live process. Status vocabulary: IMPLEMENTED, TESTED, VERIFIED (lab-measured, artifact in `benchmarks/phase6/`), MANAGED_BY_PLATFORM, SIMULATED, PLANNED, BLOCKED, NOT_REQUIRED.

| Document | Purpose |
|---|---|
| TOPIC_CATALOGUE | 20 topics: decision + status + evidence |
| IMPLEMENTATION_MATRIX / TEST_MATRIX | topic → code → tests |
| ADVANCED_ARCHITECTURE_MAP | components, persistence selection matrix |
| DATABASE_DESIGN (+ ../../phase-6/DATABASE_DESIGN.md) · DATABASE_PERFORMANCE · CONSISTENCY_MODEL | data topics 21–28 |
| STORAGE / SEARCH / REALTIME / OBSERVABILITY | delivery topics 30–36 |
| SLO_AND_ERROR_BUDGETS · SECURITY_AND_KEY_MANAGEMENT · MULTI_REGION_DECISION · DISASTER_RECOVERY | operations 37–40 |
| BENCHMARK_RESULTS · REFERENCES | measured numbers; reference status |
| EXECUTION_STATE · WORKLOG · DECISION_LOG · OPEN_ISSUES · TEST_EVIDENCE | session continuity |

Not claimed anywhere: PostgreSQL measurements, zero-downtime migration, production RTO/RPO, CDN hit ratios, deployed replicas/regions/search/real-time, KMS, malware scanning, external telemetry export.
