# Topic Catalogue (21–40)

| # | Topic | Decision | Status | Real evidence |
|---|---|---|---|---|
| 21 | Database design | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | integrity lab (6 probes); gap O-1 recorded |
| 22 | Indexing | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | 3 indexes adopted (v5), 1 rejected |
| 23 | ACID/MVCC/isolation | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | 24-thread contention; atomic UPDATE + CHECK |
| 24 | Connection pooling | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | env-tunable PG pool; saturation lab |
| 25 | Replication | MANAGED BY PLATFORM | SIMULATED, TESTED, PLANNED | routing simulation; no replica |
| 26 | Sharding | NOT REQUIRED | SIMULATED, TESTED, NOT_REQUIRED | skew simulation |
| 27 | CAP / consistency | SIMULATED (+ matrix) | SIMULATED, TESTED | CP vs AP model |
| 28 | Locks / leases / fencing | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | `scheduled_jobs.fence`; regression test |
| 29 | Polyglot persistence | NOT REQUIRED | NOT_REQUIRED, PLANNED | selection matrix only |
| 30 | Object storage | PREPARE FOR SCALE | IMPLEMENTED(module), TESTED, VERIFIED, PLANNED(routes) | 9 hostile attempts |
| 31 | CDN / edge | MANAGED BY PLATFORM | IMPLEMENTED(headers), TESTED, SIMULATED | `no-store` on /api |
| 32 | Search | PREPARE FOR SCALE | TESTED, VERIFIED(lab), PLANNED | FTS5 lab |
| 33 | Real-time | PREPARE FOR SCALE | SIMULATED, TESTED, PLANNED | protocol model; polling in use |
| 34 | Streaming / backpressure | PREPARE FOR SCALE | TESTED, VERIFIED(lab), PLANNED | 4 policies measured |
| 35 | Schema evolution | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | v5 expand-only; full cycle lab |
| 36 | Observability | IMPLEMENT NOW | IMPLEMENTED, TESTED, VERIFIED | spans, redaction, headers |
| 37 | SLI/SLO | IMPLEMENT NOW | IMPLEMENTED, TESTED, PLANNED(targets) | live SLI; candidate SLO only |
| 38 | Secrets / keys | IMPLEMENT NOW (library) | IMPLEMENTED, TESTED, VERIFIED, BLOCKED(KMS) | keyring rotation lab |
| 39 | Multi-region | NOT REQUIRED | SIMULATED, TESTED, NOT_REQUIRED | residency policy model |
| 40 | Backup/DR | IMPLEMENT NOW (drill) | IMPLEMENTED, TESTED, VERIFIED, PLANNED(scheduling) | restore drill, 8 invariants |
