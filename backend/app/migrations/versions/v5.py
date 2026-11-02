"""Migration v5: Phase VI — evidence-gated indexes + scheduler fencing token.

Additive and idempotent (expand phase only): old application instances keep
working because nothing is dropped or renamed. Fresh databases receive the
same objects from ORM metadata (v1).

Indexes (adopted only where docs/system-design/advanced/DATABASE_PERFORMANCE.md
shows planner use + >=1.5x median speedup):
  ix_requests_org_status_urgency, ix_agent_exec_org_created, ix_movements_request
REJECTED by the same experiment (1.13x, 1.5 MB): (org, depot, item, id DESC) ledger index.
"""
from sqlalchemy import text


def _has_column(conn, table, column):
    if conn.dialect.name == "sqlite":
        return any(r[1] == column for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall())
    rows = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
                        {"t": table}).fetchall()
    return any(r[0] == column for r in rows)


def upgrade(conn):
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_requests_org_status_urgency "
                      "ON aid_requests (org_id, status, urgency_score DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_exec_org_created "
                      "ON agent_executions (org_id, created_at DESC)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_movements_request "
                      "ON inventory_movements (request_id)"))
    if not _has_column(conn, "scheduled_jobs", "fence"):
        conn.execute(text("ALTER TABLE scheduled_jobs ADD COLUMN fence BIGINT NOT NULL DEFAULT 0"))
