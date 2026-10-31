"""Migration v4: Phase V — durable scheduler table (topic 20).

Fresh databases receive the table from ORM metadata; this upgrades existing
databases. Idempotent.
"""
from sqlalchemy import text


def upgrade(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            job_name VARCHAR(64) PRIMARY KEY,
            interval_seconds INTEGER DEFAULT 3600,
            last_run_at TIMESTAMP NULL,
            last_status VARCHAR(32) NULL,
            last_error TEXT NULL,
            runs INTEGER DEFAULT 0,
            lock_token VARCHAR(32) NULL,
            lock_expires_at TIMESTAMP NULL
        )"""))
