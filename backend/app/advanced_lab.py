"""
AIDNEXUS ONE — Phase VI advanced system-design laboratory.

Every experiment runs against a DISPOSABLE SQLite database created in a temp
directory (never the live database, never production). Experiments that call
production code paths (persistence.apply_inventory_movement, the real ORM
schema, the real audit-chain verifier) say so in `implementation_under_test`.
Experiments that model infrastructure we do not run (replicas, regions) are
returned with mode="SIMULATED" and are labelled as such in the UI.

Honesty rules:
  * Nothing here is hardcoded: every number is measured when the experiment runs.
  * The engine under test is SQLite (WAL). PostgreSQL-specific behavior (MVCC
    isolation levels, EXPLAIN ANALYZE, pg_stat) is NOT measured here.
  * Results record seed, sample size, environment and limitations.
"""
from __future__ import annotations

import os
import platform
import random
import shutil
import sqlite3
import statistics
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List

from sqlalchemy import text, select, func
from sqlalchemy.exc import IntegrityError, TimeoutError as SATimeout
from sqlalchemy.pool import QueuePool

from .db import build_engine, build_session_factory, run_migrations
from .models_db import (Organization, Depot, InventoryItem, InventoryMovement, Membership, User,
                        AidRequestRow, AuditEventRow, AgentExecutionRow)
from . import persistence

LAB_SEED = 42

# Evidence-gated candidate indexes (see docs/system-design/advanced/DATABASE_PERFORMANCE.md).
# name -> (table, column list SQL). Shared by the experiment and migration v5.
CANDIDATE_INDEXES = {
    "ix_requests_org_status_urgency": ("aid_requests", "org_id, status, urgency_score DESC"),
    "ix_agent_exec_org_created": ("agent_executions", "org_id, created_at DESC"),
    "ix_movements_request": ("inventory_movements", "request_id"),
    "ix_movements_org_depot_item_id": ("inventory_movements", "org_id, depot_id, item_type, id DESC"),
}


def environment() -> Dict[str, Any]:
    return {"engine": f"sqlite {sqlite3.sqlite_version}", "python": platform.python_version(),
            "os": platform.platform(), "cpu_count": os.cpu_count(),
            "database": "disposable temp file (WAL)", "production_database_touched": False}


def percentile(values: List[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def summarize(ms: List[float]) -> Dict[str, Any]:
    return {"n": len(ms), "median_ms": round(statistics.median(ms), 4),
            "p95_ms": round(percentile(ms, 95), 4),
            "p99_ms": round(percentile(ms, 99), 4) if len(ms) >= 100 else "NOT_MEASURED (n<100)",
            "min_ms": round(min(ms), 4), "max_ms": round(max(ms), 4)}


@contextmanager
def disposable_db(name: str = "lab"):
    """Fresh migrated database in a temp dir; removed afterwards."""
    d = tempfile.mkdtemp(prefix=f"aidnexus_{name}_")
    path = os.path.join(d, f"{name}.db")
    engine = build_engine(f"sqlite:///{path}")
    run_migrations(engine)
    try:
        yield engine, build_session_factory(engine), path
    finally:
        engine.dispose()
        shutil.rmtree(d, ignore_errors=True)


def _seed_orgs(session, org_ids=("ORG-A", "ORG-B")):
    for o in org_ids:
        session.add(Organization(id=o, name=o, slug=o.lower()))
    session.flush()


# ---------------------------------------------------------------------------
# Topic 21 — integrity probe (FK, unique, check, cross-tenant, delete behaviour)
# ---------------------------------------------------------------------------
def integrity_probe() -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def expect_rejected(label, fn, expect_reject=True, note=""):
        with disposable_db("integrity") as (engine, factory, _):
            with factory() as s:
                _seed_orgs(s)
                persistence.ensure_depot(s, "ORG-A", "D1")
                persistence.ensure_depot(s, "ORG-B", "D1")
                s.commit()
            rejected, detail = False, ""
            with factory() as s:
                try:
                    fn(s)
                    s.commit()
                except IntegrityError as e:
                    rejected, detail = True, str(e.orig)[:80]
                    s.rollback()
            checks.append({"check": label, "database_rejected": rejected,
                           "expected_rejection": expect_reject,
                           "pass": rejected == expect_reject, "detail": detail, "note": note})

    expect_rejected("invalid foreign key (depot -> missing org)",
                    lambda s: s.add(Depot(id="X", org_id="NOPE", name="x", lat=0, lng=0)))
    expect_rejected("duplicate membership (user, org)",
                    lambda s: (s.add(User(id="U1", email="u@example.dev", display_name="u")),
                               s.flush(),
                               s.add(Membership(user_id="U1", org_id="ORG-A", role="NGO_ADMIN")),
                               s.add(Membership(user_id="U1", org_id="ORG-A", role="AUDITOR")),
                               s.flush()))
    expect_rejected("negative inventory (CHECK quantity >= 0)",
                    lambda s: s.add(InventoryItem(depot_id="ORG-A:D1", org_id="ORG-A",
                                                  item_type="water", quantity=-1)))
    expect_rejected("duplicate inventory idempotency key",
                    lambda s: (s.add(InventoryMovement(org_id="ORG-A", depot_id="ORG-A:D1", item_type="water",
                                                       delta=1, reason="SEED", idempotency_key="k")),
                               s.flush(),
                               s.add(InventoryMovement(org_id="ORG-A", depot_id="ORG-A:D1", item_type="water",
                                                       delta=1, reason="SEED", idempotency_key="k")),
                               s.flush()))
    # Known structural gap: inventory.depot_id FK is single-column, so a row can
    # claim org B while pointing at org A's depot. We EXPECT the DB to accept it
    # today (expect_reject=False documents the gap; application layer qualifies
    # ids via q_depot). Fixing it needs a composite FK = expand/contract migration.
    expect_rejected("cross-tenant inventory row (org B row on org A depot)",
                    lambda s: s.add(InventoryItem(depot_id="ORG-A:D1", org_id="ORG-B",
                                                  item_type="water", quantity=1)),
                    expect_reject=False,
                    note="KNOWN GAP: DB accepts it; enforced only by application-layer id qualification. See OPEN_ISSUES.")

    # Deletion behaviour: deleting an org cascades to depots/inventory (ON DELETE CASCADE);
    # inventory_movements.depot_id has NO cascade -> delete of a depot with history is blocked.
    with disposable_db("integrity_del") as (engine, factory, _):
        with factory() as s:
            _seed_orgs(s)
            persistence.ensure_depot(s, "ORG-A", "D1")
            persistence.seed_inventory(s, "ORG-A", "D1", "water", 10)
            s.commit()
        with factory() as s:
            blocked = False
            try:
                s.execute(text("DELETE FROM depots WHERE id='ORG-A:D1'"))
                s.commit()
            except IntegrityError:
                blocked = True
                s.rollback()
        checks.append({"check": "delete depot that has movement history is blocked (RESTRICT)",
                       "database_rejected": blocked, "expected_rejection": True,
                       "pass": blocked, "detail": "ledger rows reference depot", "note": ""})
    return {"topic": 21, "mode": "REAL_MEASURED", "implementation_under_test": "app/models_db.py schema via migrations v1-v5",
            "environment": environment(), "checks": checks,
            "all_pass": all(c["pass"] for c in checks)}


# ---------------------------------------------------------------------------
# Topic 22 — index experiment (evidence-gated)
# ---------------------------------------------------------------------------
def _plan(conn, sql: str, params: dict) -> List[str]:
    rows = conn.execute(text("EXPLAIN QUERY PLAN " + sql), params).fetchall()
    return [r[-1] for r in rows]


def _time_query(conn, sql: str, params: dict, repeats: int) -> Dict[str, Any]:
    ms = []
    nrows = 0
    for _ in range(repeats):
        t = time.perf_counter()
        nrows = len(conn.execute(text(sql), params).fetchall())
        ms.append((time.perf_counter() - t) * 1000)
    out = summarize(ms)
    out["rows_returned"] = nrows
    return out


def _index_bytes(conn, name: str):
    try:
        return conn.execute(text("SELECT SUM(pgsize) FROM dbstat WHERE name=:n"), {"n": name}).scalar()
    except Exception:  # dbstat not compiled in
        return None


def index_experiment(n_requests: int = 20000, n_exec: int = 20000, n_moves: int = 40000,
                     repeats: int = 40, seed: int = LAB_SEED) -> Dict[str, Any]:
    rnd = random.Random(seed)
    queries = {
        "mission_dashboard (org+status, order urgency desc, page 50)": (
            "SELECT id, urgency_score FROM aid_requests WHERE org_id=:o AND status=:st "
            "ORDER BY urgency_score DESC LIMIT 50", {"o": "ORG-A", "st": "PENDING"}),
        "agent_execution_history (org, newest 50)": (
            "SELECT id, agent_id, created_at FROM agent_executions WHERE org_id=:o "
            "ORDER BY created_at DESC LIMIT 50", {"o": "ORG-A"}),
        "beneficiary_case_history (movements by request_id)": (
            "SELECT id, delta FROM inventory_movements WHERE request_id=:r", {"r": "REQ-777"}),
        "inventory_ledger_page (org, depot, item, newest 50)": (
            "SELECT id, delta FROM inventory_movements WHERE org_id=:o AND depot_id=:d AND item_type=:i "
            "ORDER BY id DESC LIMIT 50", {"o": "ORG-A", "d": "ORG-A:D1", "i": "water"}),
        "audit_timeline (org, newest 50)": (
            "SELECT seq, event_type FROM audit_events WHERE org_id=:o ORDER BY seq DESC LIMIT 50",
            {"o": "ORG-A"}),
    }
    with disposable_db("index") as (engine, factory, path):
        with engine.begin() as c:
            for ix in CANDIDATE_INDEXES:           # baseline = no candidate indexes
                c.execute(text(f"DROP INDEX IF EXISTS {ix}"))
        with factory() as s:
            _seed_orgs(s)
            persistence.ensure_depot(s, "ORG-A", "D1")
            persistence.ensure_depot(s, "ORG-B", "D1")
            s.commit()
        raw = engine.raw_connection()
        cur = raw.cursor()
        cur.execute("BEGIN")
        for i in range(n_requests):
            o = "ORG-A" if i % 2 == 0 else "ORG-B"
            cur.execute("INSERT INTO aid_requests (id,org_id,requester_name,lat,lng,sector,priority,status,"
                        "deadline_hours,affected_people,urgency_score,intake_channel,created_at,items) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"{o}:R{i}", o, "synthetic", 0.0, 0.0, "S", "HIGH",
                         rnd.choice(["PENDING", "PENDING", "DISPATCHED", "DELIVERED"]), 24.0, 5,
                         round(rnd.uniform(0, 100), 2), "MANUAL", float(i), "[]"))
        for i in range(n_exec):
            o = "ORG-A" if i % 2 == 0 else "ORG-B"
            cur.execute("INSERT INTO agent_executions (execution_id,org_id,agent_id,action_id,status,provider,"
                        "prompt_version,context_version,context,output,postcondition_ok,latency_ms,token_usage,created_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"E{i}", o, "agent-1", "act", "SUCCEEDED", "deterministic", "", "", "{}", "{}", 1, 5, "{}",
                         f"2026-01-01 00:{(i // 60) % 60:02d}:{i % 60:02d}.{i:06d}"))
        for i in range(n_moves):
            o = "ORG-A" if i % 2 == 0 else "ORG-B"
            cur.execute("INSERT INTO inventory_movements (org_id,depot_id,item_type,delta,reason,request_id,"
                        "idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (o, f"{o}:D1", rnd.choice(["water", "food"]), 1.0, "DELIVERY",
                         f"REQ-{rnd.randint(0, 5000)}", f"k{i}", "2026-01-01 00:00:00"))
        for i in range(n_exec // 4):
            cur.execute("INSERT INTO audit_events (org_id,seq,event_type,actor_id,actor_type,entity_type,entity_id,"
                        "summary,details,sha256,prev_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("ORG-A", i + 1, "E", "a", "SYSTEM", "t", "x", "s", "{}", f"h{i}", "", "2026-01-01 00:00:00"))
        cur.execute("COMMIT")
        raw.close()

        def measure(label_conn):
            out = {}
            for name, (sql, params) in queries.items():
                out[name] = {"plan": _plan(label_conn, sql, params),
                             "timing": _time_query(label_conn, sql, params, repeats)}
            return out

        with engine.connect() as conn:
            before = measure(conn)

        # Write overhead: time inserting 3000 movement rows with / without the candidate indexes.
        def insert_batch(tag):
            raw2 = engine.raw_connection()
            c2 = raw2.cursor()
            t = time.perf_counter()
            c2.execute("BEGIN")
            for i in range(3000):
                c2.execute("INSERT INTO inventory_movements (org_id,depot_id,item_type,delta,reason,request_id,"
                           "idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?)",
                           ("ORG-A", "ORG-A:D1", "water", 1.0, "DELIVERY", f"WRITEBATCH-{i}", f"{tag}{i}", "2026-01-01"))
            c2.execute("COMMIT")
            dt = (time.perf_counter() - t) * 1000
            raw2.close()
            return dt

        write_before_ms = insert_batch("wb")
        with engine.begin() as c:
            for ix, (tbl, cols) in CANDIDATE_INDEXES.items():
                c.execute(text(f"CREATE INDEX IF NOT EXISTS {ix} ON {tbl} ({cols})"))
            c.execute(text("ANALYZE"))
        write_after_ms = insert_batch("wa")

        with engine.connect() as conn:
            after = measure(conn)
            sizes = {ix: _index_bytes(conn, ix) for ix in CANDIDATE_INDEXES}

        verdicts = {}
        for q in queries:
            bplan, aplan = " | ".join(before[q]["plan"]), " | ".join(after[q]["plan"])
            used = any(ix in aplan for ix in CANDIDATE_INDEXES)
            speedup = before[q]["timing"]["median_ms"] / max(after[q]["timing"]["median_ms"], 1e-9)
            same_rows = before[q]["timing"]["rows_returned"] == after[q]["timing"]["rows_returned"]
            verdicts[q] = {"candidate_index_used": used, "median_speedup_x": round(speedup, 2),
                           "results_identical_rowcount": same_rows,
                           "evidence_supports_index": bool(used and speedup >= 1.5 and same_rows)}
        # Adopt only evidence-supported indexes; drop the rest and re-measure write cost.
        adopted = {}
        ix_by_query = {"mission_dashboard": "ix_requests_org_status_urgency",
                       "agent_execution_history": "ix_agent_exec_org_created",
                       "beneficiary_case_history": "ix_movements_request",
                       "inventory_ledger_page": "ix_movements_org_depot_item_id"}
        for q, v in verdicts.items():
            ix = next((i for k, i in ix_by_query.items() if q.startswith(k)), None)
            if ix:   # audit_timeline is already served by uq_audit_org_seq: no new index needed
                adopted[ix] = v["evidence_supports_index"]
        with engine.begin() as c:
            for ix, ok in adopted.items():
                if not ok:
                    c.execute(text(f"DROP INDEX IF EXISTS {ix}"))
        write_adopted_ms = insert_batch("wf")
        return {"topic": 22, "mode": "REAL_MEASURED", "seed": seed, "adopted_indexes": adopted,
                "implementation_under_test": "ORM schema + CANDIDATE_INDEXES (SQLite EXPLAIN QUERY PLAN)",
                "environment": environment(),
                "dataset": {"aid_requests": n_requests, "agent_executions": n_exec,
                            "inventory_movements": n_moves + 3000, "audit_events": n_exec // 4},
                "repeats": repeats, "before": before, "after": after, "verdicts": verdicts,
                "write_overhead": {"batch_rows": 3000, "insert_ms_without_candidate_indexes": round(write_before_ms, 1),
                                   "insert_ms_with_candidate_indexes": round(write_after_ms, 1),
                                   "overhead_pct_all_candidates": round((write_after_ms / write_before_ms - 1) * 100, 1),
                                   "insert_ms_with_adopted_set_only": round(write_adopted_ms, 1),
                                   "overhead_pct_adopted_set": round((write_adopted_ms / write_before_ms - 1) * 100, 1),
                                   "note": "sequential batches on a growing table; small absolute numbers, treat as indicative"},
                "index_size_bytes": sizes,
                "limitations": ["SQLite planner/timings, not PostgreSQL", "single process, warm page cache",
                                "synthetic data distribution (seeded uniform)"]}


# ---------------------------------------------------------------------------
# Topic 23 — concurrency: real persistence.apply_inventory_movement under threads
# ---------------------------------------------------------------------------
def inventory_contention(stock: int = 100, workers: int = 24, qty: int = 10, seed: int = LAB_SEED) -> Dict[str, Any]:
    """`workers` threads each try to deduct `qty` from `stock` using the PRODUCTION
    function. Oversell is impossible iff successes*qty <= stock and final >= 0."""
    with disposable_db("contention") as (engine, factory, _):
        with factory() as s:
            _seed_orgs(s, ("ORG-A",))
            persistence.ensure_depot(s, "ORG-A", "D1")
            persistence.seed_inventory(s, "ORG-A", "D1", "water", stock)
            s.commit()
        results = {"ok": 0, "rejected_negative": 0, "other_error": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(workers)
        latencies: List[float] = []

        def worker(i: int):
            barrier.wait()
            t = time.perf_counter()
            outcome = "other_error"
            for attempt in range(5):  # retry only on lock contention, never on constraint rejection
                try:
                    with factory() as s:
                        persistence.apply_inventory_movement(s, "ORG-A", "D1", "water", -float(qty), "DELIVERY",
                                                             request_id=f"R{i}", idempotency_key=f"lab:{i}")
                        s.commit()
                    outcome = "ok"
                    break
                except IntegrityError:
                    outcome = "rejected_negative"
                    break
                except Exception as e:  # noqa: BLE001
                    if "locked" in str(e).lower():
                        time.sleep(0.02 * (attempt + 1))
                        continue
                    break
            with lock:
                results[outcome] += 1
                latencies.append((time.perf_counter() - t) * 1000)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        with factory() as s:
            final = s.execute(select(InventoryItem.quantity)).scalar_one()
            ledger = s.execute(select(func.coalesce(func.sum(InventoryMovement.delta), 0))).scalar_one()
        expected_ok = min(workers, stock // qty)
        return {"topic": 23, "mode": "REAL_MEASURED",
                "implementation_under_test": "persistence.apply_inventory_movement (atomic UPDATE quantity=quantity+delta + CHECK)",
                "environment": environment(), "workers": workers, "initial_stock": stock, "qty_each": qty,
                "outcomes": results, "final_stock": final, "ledger_sum": ledger,
                "expected_successes": expected_ok,
                "invariants": {"never_negative": final >= 0,
                               "ledger_matches_stock": abs(ledger - final) < 1e-9,
                               "successes_match_capacity": results["ok"] == expected_ok},
                "latency": summarize(latencies),
                "limitations": ["SQLite serialises writers (single-writer); PostgreSQL would use row locks / MVCC",
                                "isolation levels not varied; correctness comes from atomic UPDATE + CHECK, not from SERIALIZABLE"]}


# ---------------------------------------------------------------------------
# Topic 24 — pool saturation + pool budget
# ---------------------------------------------------------------------------
def pool_budget(db_max_connections: int, reserved: int, replicas: int, workers_per_replica: int,
                scheduled_extra: int = 1) -> Dict[str, Any]:
    """Per-process (pool_size + max_overflow) must satisfy
    processes * per_process + reserved + scheduled_extra <= db_max_connections."""
    processes = replicas * workers_per_replica
    usable = db_max_connections - reserved - scheduled_extra * replicas
    per_process = max(0, usable // max(processes, 1))
    return {"processes": processes, "usable_connections": usable, "max_per_process": per_process,
            "feasible": per_process >= 1,
            "formula": "floor((db_max - reserved - scheduled_extra*replicas) / (replicas*workers))"}


def pool_saturation(pool_size: int = 3, clients: int = 12, hold_s: float = 0.15, timeout_s: float = 0.25) -> Dict[str, Any]:
    d = tempfile.mkdtemp(prefix="aidnexus_pool_")
    path = os.path.join(d, "pool.db")
    sqlite3.connect(path).close()
    from sqlalchemy import create_engine
    eng = create_engine(f"sqlite:///{path}", poolclass=QueuePool, pool_size=pool_size, max_overflow=0,
                        pool_timeout=timeout_s, connect_args={"check_same_thread": False})
    waits: List[float] = []
    outcomes = {"served": 0, "timed_out": 0}
    lock = threading.Lock()
    peak = {"in_use": 0}

    def client():
        t = time.perf_counter()
        try:
            conn = eng.connect()
            w = (time.perf_counter() - t) * 1000
            with lock:
                peak["in_use"] = max(peak["in_use"], eng.pool.checkedout())
            time.sleep(hold_s)
            conn.close()
            with lock:
                outcomes["served"] += 1
                waits.append(w)
        except SATimeout:
            with lock:
                outcomes["timed_out"] += 1
                waits.append((time.perf_counter() - t) * 1000)

    try:
        ts = [threading.Thread(target=client) for _ in range(clients)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        time.sleep(0.05)
        t = time.perf_counter()
        conn = eng.connect()   # recovery probe: pool must serve again once load stops
        conn.execute(text("SELECT 1"))
        conn.close()
        recovery_ms = (time.perf_counter() - t) * 1000
        leaked = eng.pool.checkedout()
    finally:
        eng.dispose()
        shutil.rmtree(d, ignore_errors=True)
    return {"topic": 24, "mode": "REAL_MEASURED",
            "implementation_under_test": "sqlalchemy QueuePool configured like app.db.build_engine (env-tunable)",
            "environment": environment(), "pool_size": pool_size, "max_overflow": 0, "clients": clients,
            "hold_s": hold_s, "pool_timeout_s": timeout_s, "outcomes": outcomes,
            "peak_checked_out": peak["in_use"], "pool_wait": summarize(waits),
            "leaked_connections_after": leaked, "recovery_probe_ms": round(recovery_ms, 3),
            "invariants": {"never_exceeded_pool_size": peak["in_use"] <= pool_size,
                           "excess_clients_failed_fast": outcomes["timed_out"] > 0,
                           "no_leaks": leaked == 0, "recovered": True},
            "budget_example": pool_budget(100, 10, 3, 2)}
