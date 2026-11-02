# Advanced Architecture Map

Live components (real): FastAPI app → rate limit → request_context (trace, no-store) → auth → handlers → SQLAlchemy (instrumented, bounded pool on PG) → SQLite/PostgreSQL. Outbox + fenced scheduler. In-process telemetry ring buffers.

Not deployed (labelled in the UI): read replica, CDN, real-time server, search index, KMS, regional deployments, external observability backend. Object store: module only, not wired.

## Persistence selection matrix
| Need | Choice | Query | Consistency | Ops complexity | Cost | Security | Volume | Backup | Failure behaviour |
|---|---|---|---|---|---|---|---|---|---|
| Mission state, inventory, approvals, receipts | **Relational** (selected) | joins, constraints | strong | low | low | RBAC+tenant | small-medium | DB backup/PITR | fail closed |
| Documents/photos | Object storage (module ready) | by key | read-after-write per bucket | medium | low | signed URLs | grows | bucket versioning | checksum failure → refuse |
| Free-text search | relational FTS first | text | eventual, re-checked | low | low | org filter | small | rebuildable | degrade to DB |
| Semantic evidence | vector DB — **not adopted** | similarity | eventual | high | medium | embedding leakage | n/a | rebuildable | no use case (agents deterministic) |
| Telemetry | in-memory now; TSDB if scale | time-range | eventual | high | medium | PII redaction | small | not needed | lost on restart (documented) |
| Relationship analysis | graph DB — **not adopted** | traversal | — | high | medium | — | n/a | — | no graph queries exist |
Source of truth is the relational DB; every other store is derived or blob.
