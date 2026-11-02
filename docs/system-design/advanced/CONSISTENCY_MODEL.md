# Consistency & Isolation (Topics 23, 25, 27)

## Required guarantees per operation
| Operation | Needs | Mechanism today | Stronger isolation needed? |
|---|---|---|---|
| Inventory reservation / deduction | no lost update, never negative | one atomic `UPDATE qty = qty + δ` + CHECK + ledger row with UNIQUE key, one transaction | No (single-row invariant) |
| Delivery confirmation | exactly-once effect | receipt PK + ledger idempotency key; duplicate returns original | No |
| Plan approval | bind to authoritative version | approval targets pending `version_id`; UNIQUE(org,version) | No; app-level state check |
| Dispatch creation | follows approved active plan | state machine ALLOWED_TRANSITIONS | No |
| Resource transfer (2 orgs, 2 rows) | atomic debit+credit, no write skew | one transaction (Phase IV) | On PostgreSQL: row locks / SERIALIZABLE with retry — **not verified on PG** |
| Procurement receipt | idempotent credit | ledger key | No |
Verified: 24 threads × 10 units vs 100 stock → exactly 10 succeed, 14 rejected, final 0, ledger sum = stock; 5/5 runs. With stock 35 → 3 succeed, 5 left. Rollback on constraint failure leaves no ledger row. Process-kill durability: SQLite WAL durability was not crash-tested (no kill -9 experiment) — NOT_MEASURED.
MVCC/dirty-read/phantom/write-skew demonstrations on PostgreSQL: **not run** (no server). SQLite is single-writer.

## Replica read routing (simulation)
Strong (primary only): inventory availability, delivery confirmation, plan approval, mission state, audit verification. May be stale (labelled): historical reports, some analytics, search. Read-your-writes via min-version token. Async failover loses un-replicated acknowledged writes (sim: 1).

## CAP matrix
| Operation | During partition |
|---|---|
| Reservation, delivery, approval | reject (CP) — model: CP reserves 0 vs AP reserves 16 of 10 |
| Analytics, history | serve stale, labelled |
| Search | serve stale or degrade to DB; never authoritative |
AIDNEXUS has a single primary, so divergent writes cannot occur; the model explains what a multi-node design would trade.
