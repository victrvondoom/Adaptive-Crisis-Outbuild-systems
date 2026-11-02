"""
AIDNEXUS ONE — Database engine, session management, and migration runner.

Production: PostgreSQL via DATABASE_URL (psycopg driver installed).
Local dev / CI: SQLite (WAL mode, busy-timeout) — same ORM models, same code.

The migration runner is deliberately lightweight: numbered, ordered migration
modules under app/migrations/versions executed exactly once, tracked in the
schema_migrations table. Every migration runs in a transaction (where the
dialect supports DDL transactions).
"""
import os
import logging
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

logger = logging.getLogger("aidnexus.db")

DEFAULT_SQLITE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "aidnexus.db"))


class Base(DeclarativeBase):
    pass


def _configure_sqlite(engine):
    """WAL + busy timeout so concurrent writers serialize instead of erroring."""
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()


def build_engine(database_url: Optional[str] = None, echo: bool = False):
    url = database_url or os.environ.get("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_dir = os.path.dirname(url.replace("sqlite:///", "", 1))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    kwargs = dict(echo=echo, future=True, pool_pre_ping=True, pool_recycle=1800)
    if not url.startswith("sqlite"):
        # Phase VI: bounded, env-tunable pool. Budget MUST satisfy
        #   replicas * workers * (pool_size + max_overflow) + reserved <= db max_connections
        # (see advanced_lab.pool_budget). Defaults are conservative, not a tuned claim.
        kwargs.update(pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
                      max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "5")),
                      pool_timeout=float(os.environ.get("DB_POOL_TIMEOUT", "10")))
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _configure_sqlite(engine)
    _instrument_queries(engine)
    return engine


def _instrument_queries(engine):
    """Phase VI: one `db.query` leaf span per statement (verb only; never SQL parameters)."""
    import time as _t
    from .telemetry import record_leaf_span

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        context._aid_t0 = _t.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        t0 = getattr(context, "_aid_t0", None)
        if t0 is not None:
            record_leaf_span("db.query", (_t.perf_counter() - t0) * 1000,
                             verb=statement.lstrip().split(" ", 1)[0].upper()[:10])

    @event.listens_for(engine, "handle_error")
    def _err(exc_context):
        ctx = exc_context.execution_context
        t0 = getattr(ctx, "_aid_t0", None) if ctx is not None else None
        if t0 is not None:
            record_leaf_span("db.query", (_t.perf_counter() - t0) * 1000, status="ERROR",
                             error_class=type(exc_context.original_exception).__name__, verb="ERR")


def build_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = build_session_factory(get_engine())
    return _SessionFactory


@contextmanager
def session_scope():
    """Transactional scope: commit on success, rollback on error."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ----------------------------------------------------------------------
# Migration runner
# ----------------------------------------------------------------------
MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(32) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def run_migrations(engine, migrations_pkg="app.migrations.versions") -> list:
    """Applies pending migrations in version order, exactly once each.
    Returns the list of applied version ids (empty when up to date)."""
    from importlib import import_module
    with engine.begin() as conn:
        conn.execute(text(MIGRATIONS_TABLE_DDL))
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        applied = {r[0] for r in rows}

    import pkgutil
    mod = import_module(migrations_pkg)
    versions = sorted(
        (mi.name for mi in pkgutil.iter_modules(mod.__path__)
         if mi.name.startswith("v") and mi.name[1:].isdigit()),
        key=lambda n: int(n[1:]),
    )

    newly_applied = []
    for v in versions:
        if v in applied:
            continue
        migration = import_module(f"{migrations_pkg}.{v}")
        upgrade = getattr(migration, "upgrade")
        with engine.begin() as conn:  # transactional DDL (SQLite/Postgres support it)
            upgrade(conn)
            conn.execute(text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": v})
        newly_applied.append(v)
        logger.info("applied migration %s", v)
    return newly_applied
