"""Migration v2: Phase III features — inventory expiry, volunteer certification
expiry, case notes, approval delegations.

Idempotent: column adds check existence first (v1 emits current ORM metadata on
fresh databases, which may already contain the new columns).
"""
from sqlalchemy import text, inspect


def _has_column(conn, table, column):
    """Read-only probe that works inside a migration transaction."""
    if conn.dialect.name == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    rows = conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": table}).fetchall()
    return any(r[0] == column for r in rows)


def upgrade(conn):
    if not _has_column(conn, "inventory_items", "expires_at"):
        conn.execute(text("ALTER TABLE inventory_items ADD COLUMN expires_at TIMESTAMP NULL"))
    if not _has_column(conn, "volunteers", "certification_expires_at"):
        conn.execute(text("ALTER TABLE volunteers ADD COLUMN certification_expires_at TIMESTAMP NULL"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS case_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            request_id VARCHAR(64) NOT NULL,
            author_user_id VARCHAR(32) NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_case_notes_org_req ON case_notes (org_id, request_id)"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS approval_delegations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            delegator_user_id VARCHAR(32) NOT NULL,
            delegate_user_id VARCHAR(32) NOT NULL,
            permission VARCHAR(64) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_delegations_org ON approval_delegations (org_id, delegate_user_id)"))
