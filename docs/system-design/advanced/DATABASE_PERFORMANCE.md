# Database Performance (Topics 22, 24)

Method: disposable SQLite 3.53 DB (WAL), schema from migrations, candidate indexes dropped for baseline, seeded data (seed 42): 20,000 aid_requests, 20,000 agent_executions, 40,000(+3,000) inventory_movements, 5,000 audit_events. 40 repeats/query; `EXPLAIN QUERY PLAN` captured. Gate: planner uses index AND median speedup ≥ 1.5× AND identical row count. Artifact: `benchmarks/phase6/phase6_lab_eb6644c.json`.

| Query | Plan before → after | median ms before→after | p95 ms before→after | Speedup | Decision |
|---|---|---|---|---|---|
| Mission dashboard (org,status order urgency desc, 50) | ix_requests_org_status + TEMP B-TREE → ix_requests_org_status_urgency | 1.024→0.059 | 1.226→0.086 | 17.4× | **adopt** |
| Agent execution history | ix_agent_executions_org_id + TEMP B-TREE → ix_agent_exec_org_created | 2.382→0.060 | 2.546→0.108 | 39.4× | **adopt** |
| Case history by request_id | SCAN inventory_movements → ix_movements_request | 1.976→0.036 | 2.189→0.038 | 55.0× | **adopt** |
| Inventory ledger page | org index → (org,depot,item,id DESC) | 0.068→0.062 | 0.085→0.078 | 1.11× | **reject** (1.56 MB) |
| Audit timeline | uq_audit_org_seq already used | 0.053→0.054 | — | 0.98× | none needed |

Index sizes (dbstat): 0.64 MB, 0.82 MB, 0.81 MB adopted; 1.56 MB rejected. Write overhead (3,000-row insert batch): all four candidates +244%; adopted three only **+0.5%** (sequential batches on a growing table; tiny absolute values — indicative only).
Limits: SQLite not PostgreSQL; warm cache; single process; p99 not reported (n=40). N+1: no ORM N+1 pattern was found in the hot paths inspected (state is held in memory engines; DB reads are per-org list queries) — not exhaustively proven. Lock contention from queries: not measured separately (see contention lab).
Migration `v5` adds the adopted indexes (also on fresh DBs via ORM metadata).

## Pool (topic 24)
`build_engine`: PostgreSQL gets `pool_size=DB_POOL_SIZE(5)`, `max_overflow=DB_MAX_OVERFLOW(5)`, `pool_timeout=DB_POOL_TIMEOUT(10)`; defaults are conservative placeholders, not tuned. Budget rule: `replicas × workers × (pool_size+max_overflow) + reserved ≤ db_max_connections` — `pool_budget()` solves for the per-process cap (example: 100 max, 10 reserved, 3 replicas × 2 workers → 14). Saturation lab (3-connection QueuePool, 12 clients holding 150 ms, timeout 250 ms): 6 served, 6 timed out; wait median 200 ms, p95 250 ms; peak checked-out 3 (never exceeded); 0 leaked; recovery probe OK. SQLite uses WAL + busy_timeout=10 s instead of pooling limits. Real PostgreSQL connection-limit failure was NOT run (no server).
