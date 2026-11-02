# References and verification status (2026-11-02)

The session network allow-list blocked w3.org, postgresql.org and sqlite.org (DNS failure). **No reference below was verified online this session.** Claims that depend on them are labelled "unverified" where used.
| Source | Used for | Status |
|---|---|---|
| W3C Trace Context (Recommendation) | traceparent `00-<32hex>-<16hex>-<2hex>`, all-zero ids invalid | NOT VERIFIED ONLINE (format implemented from prior knowledge; unit-tested for self-consistency only) |
| PostgreSQL docs: Transaction Isolation, Explicit Locking, FTS, Continuous Archiving/PITR, Replication | default READ COMMITTED; atomic UPDATE semantics; GIN FTS | NOT VERIFIED ONLINE; no PG server available to test |
| SQLite docs: Online Backup API, FTS5, EXPLAIN QUERY PLAN, WAL | lab engine behaviour | Behaviour observed empirically in this repo's tests (SQLite 3.53.1) |
| SQLAlchemy 2 pooling docs | QueuePool args | observed in tests |
| RFC 6455 / HTML SSE spec | transport choice | NOT VERIFIED ONLINE |
| Google SRE book (SLO/error budget) | definitions | NOT VERIFIED ONLINE |
Action: re-run verification when the domains are allowed.
