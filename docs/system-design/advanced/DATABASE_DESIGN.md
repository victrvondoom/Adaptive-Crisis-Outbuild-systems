# Database Design — summary and decisions

Full entity mapping, ER diagram and authoritative-source table: [`docs/phase-6/DATABASE_DESIGN.md`](../../phase-6/DATABASE_DESIGN.md) (single authoritative record; not duplicated here).

Decisions: ADV-ADR-021 keep transactional tables normalized; items stay JSON evidence snapshot; no new read-model tables (dispatch queue is a plan projection). ADV-ADR-026 sharding NOT REQUIRED: growth candidates in order — `audit_events`, `agent_executions`, `inventory_movements`; first tools are indexes (done), retention/archival, then time partitioning on PostgreSQL; tenant sharding last. `org_id` leads all tenant indexes, preserving that option.
Open: O-1 composite FK for cross-tenant inventory rows.
