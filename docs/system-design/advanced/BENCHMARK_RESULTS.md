# Benchmark Results (Phase VI)

Artifact: `benchmarks/phase6/phase6_lab_eb6644c.json` — commit `eb6644c`, seed 42, Linux x86_64, 4 CPUs, Python 3.13, SQLite 3.53.1, disposable temp DB (WAL). Reproduce: `cd backend && python -m app.advanced_runner`. Runs per experiment: 5 (index/schema/storage/secrets: 2). Raw results are in the JSON. p99 reported only where n≥100 (none here).
| Experiment | Result (last run; medians across runs in artifact) |
|---|---|
| Index (topic 22) | see DATABASE_PERFORMANCE.md |
| Contention (23) | 24 writers/100 stock: 10 ok / 14 rejected / final 0; per-attempt median 41.9 ms, p95 59.8 ms |
| Pool (24) | wait median 200.3 ms, p95 250.4 ms; 6 served / 6 timed out; 0 leaks |
| Lease (28) | 1 winner of 8 every run; stale holder rejected; wall ≈62 ms |
| Search (32) | 3,000 docs; query median 1.29 ms, p95 1.35 ms (n=60) |
| Backpressure (34) | see REALTIME_ARCHITECTURE.md |
| Trace (36) | ≈3.4 µs/span; 4-span trace linked |
| Backup (40) | backup 5.7 ms, restore+validate 7.2 ms, 2 events lost post-backup |
Not benchmarked (no infrastructure): PostgreSQL, real replication lag, storage upload/download over network, real-time delivery latency, CDN, multi-region failover.
Comparability: all runs same machine/engine; before/after index runs use the same dataset. Numbers vary a few % between runs (see two artifact generations: speedups 17–18×, 39–40×, 54–55×).
