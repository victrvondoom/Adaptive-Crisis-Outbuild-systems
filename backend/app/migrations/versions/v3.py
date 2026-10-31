"""Migration v3: Phase IV — beneficiary consents, cross-NGO resource transfers,
procurement (suppliers + purchase lifecycle), org procurement budget.

Fresh databases already receive these tables from ORM metadata (v1 emits
current models); this migration upgrades existing databases. Idempotent.
"""
from sqlalchemy import text


def _has_column(conn, table, column):
    if conn.dialect.name == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    rows = conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": table}).fetchall()
    return any(r[0] == column for r in rows)


def upgrade(conn):
    if not _has_column(conn, "organizations", "budget_cents"):
        conn.execute(text("ALTER TABLE organizations ADD COLUMN budget_cents INTEGER NULL"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS beneficiary_consents (
            id VARCHAR(40) PRIMARY KEY,
            org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            request_id VARCHAR(64) NOT NULL,
            consent_scope VARCHAR(64) DEFAULT 'ASSISTANCE',
            granted_by VARCHAR(200) NOT NULL,
            evidence TEXT NULL,
            granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revoked_at TIMESTAMP NULL
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_consents_org_req ON beneficiary_consents (org_id, request_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id VARCHAR(32) PRIMARY KEY,
            org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_suppliers_org ON suppliers (org_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS procurements (
            id VARCHAR(32) PRIMARY KEY,
            org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            supplier_id VARCHAR(32) NOT NULL,
            depot_id VARCHAR(32) NOT NULL,
            item_type VARCHAR(64) NOT NULL,
            quantity FLOAT NOT NULL,
            unit_cost_cents INTEGER NOT NULL,
            total_cost_cents INTEGER NOT NULL,
            status VARCHAR(32) DEFAULT 'PROPOSED',
            proposed_by VARCHAR(200) NOT NULL,
            approved_by VARCHAR(200) NULL,
            approved_at TIMESTAMP NULL,
            received_quantity FLOAT NULL,
            discrepancy_note TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            received_at TIMESTAMP NULL
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_procurements_org ON procurements (org_id, status)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS resource_transfers (
            id VARCHAR(40) PRIMARY KEY,
            source_org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            dest_org_id VARCHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source_depot_id VARCHAR(32) NOT NULL,
            dest_depot_id VARCHAR(32) NOT NULL,
            item_type VARCHAR(64) NOT NULL,
            quantity FLOAT NOT NULL,
            status VARCHAR(32) DEFAULT 'PROPOSED',
            reason TEXT NULL,
            proposed_by VARCHAR(200) NOT NULL,
            source_approved_by VARCHAR(200) NULL,
            source_approved_at TIMESTAMP NULL,
            dest_approved_by VARCHAR(200) NULL,
            dest_approved_at TIMESTAMP NULL,
            dispatched_at TIMESTAMP NULL,
            received_at TIMESTAMP NULL,
            failed_reason TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transfers_source ON resource_transfers (source_org_id, status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transfers_dest ON resource_transfers (dest_org_id, status)"))
