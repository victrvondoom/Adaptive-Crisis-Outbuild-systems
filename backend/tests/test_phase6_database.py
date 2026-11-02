"""Phase VI topics 21-24: schema integrity, evidence-gated indexes, concurrency, pooling."""
import sqlite3

import pytest
from sqlalchemy import text

from app import advanced_lab as L
from app.db import build_engine, run_migrations


def test_integrity_probe_all_checks_hold():
    r = L.integrity_probe()
    failing = [c for c in r["checks"] if not c["pass"]]
    assert not failing, failing
    gap = next(c for c in r["checks"] if c["check"].startswith("cross-tenant"))
    # The documented gap must stay visible: if the DB starts rejecting it, update the docs.
    assert gap["database_rejected"] is False and "KNOWN GAP" in gap["note"]


def test_index_experiment_adopts_only_evidence_supported_indexes():
    r = L.index_experiment(n_requests=4000, n_exec=4000, n_moves=8000, repeats=15)
    adopted = r["adopted_indexes"]
    assert adopted["ix_requests_org_status_urgency"] and adopted["ix_agent_exec_org_created"] and adopted["ix_movements_request"]
    for q, v in r["verdicts"].items():
        assert v["results_identical_rowcount"], q          # an index must never change results
    plan_after = " ".join(r["after"]["mission_dashboard (org+status, order urgency desc, page 50)"]["plan"])
    plan_before = " ".join(r["before"]["mission_dashboard (org+status, order urgency desc, page 50)"]["plan"])
    assert "TEMP B-TREE" in plan_before and "TEMP B-TREE" not in plan_after
    assert "SCAN inventory_movements" in " ".join(r["before"]["beneficiary_case_history (movements by request_id)"]["plan"])


def test_migration_v5_present_on_fresh_and_idempotent_on_upgrade(tmp_path):
    e = build_engine(f"sqlite:///{tmp_path/'m.db'}")
    run_migrations(e)
    with e.connect() as c:
        names = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='index'"))}
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(scheduled_jobs)"))}
    assert {"ix_requests_org_status_urgency", "ix_agent_exec_org_created", "ix_movements_request"} <= names
    assert "fence" in cols
    # re-applying v5 over an already-current schema must be a safe no-op
    from app.migrations.versions import v5
    with e.begin() as c:
        v5.upgrade(c)
        v5.upgrade(c)


def test_v5_upgrades_a_pre_v5_database(tmp_path):
    """Partial-migration safety: simulate a v4-era DB (no fence column, no indexes)."""
    e = build_engine(f"sqlite:///{tmp_path/'old.db'}")
    run_migrations(e)
    with e.begin() as c:
        for ix in ("ix_requests_org_status_urgency", "ix_agent_exec_org_created", "ix_movements_request"):
            c.execute(text(f"DROP INDEX {ix}"))
        c.execute(text("ALTER TABLE scheduled_jobs DROP COLUMN fence"))
        c.execute(text("DELETE FROM schema_migrations WHERE version='v5'"))
    assert run_migrations(e) == ["v5"]
    with e.connect() as c:
        assert "fence" in {r[1] for r in c.execute(text("PRAGMA table_info(scheduled_jobs)"))}


def test_concurrent_inventory_never_oversells():
    r = L.inventory_contention(stock=100, workers=24, qty=10)
    assert r["outcomes"]["ok"] == 10 and r["outcomes"]["other_error"] == 0
    assert r["final_stock"] == 0 and all(r["invariants"].values())


def test_concurrent_inventory_partial_stock():
    r = L.inventory_contention(stock=35, workers=12, qty=10)   # only 3 can succeed; 5 units stay
    assert r["outcomes"]["ok"] == 3 and r["final_stock"] == 5
    assert r["invariants"]["never_negative"]


def test_pool_saturation_fails_fast_and_recovers():
    r = L.pool_saturation(pool_size=3, clients=10, hold_s=0.15, timeout_s=0.2)
    assert all(r["invariants"].values()), r["invariants"]
    assert r["outcomes"]["served"] + r["outcomes"]["timed_out"] == 10


def test_pool_budget_formula():
    b = L.pool_budget(db_max_connections=100, reserved=10, replicas=3, workers_per_replica=2, scheduled_extra=1)
    # (100-10-3*1)/6 = 14
    assert b["max_per_process"] == 14 and b["feasible"]
    assert not L.pool_budget(10, 8, 4, 2)["feasible"]          # impossible: pool of 0 per process


def test_postgres_pool_env_is_bounded(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "2")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "1")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "3")
    e = build_engine("postgresql+psycopg://u:p@localhost:1/none")   # lazy: no connection made
    assert e.pool.size() == 2 and e.pool._max_overflow == 1 and e.pool._timeout == 3
