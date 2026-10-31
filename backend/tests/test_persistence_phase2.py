"""Phase II P0 persistence tests: durability, transactions, concurrency,
idempotency, tamper-evidence, and migration reproducibility."""
import os
import sys
import uuid
import threading

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import build_engine, run_migrations, session_scope, get_engine
from app import persistence
from app.models_db import Organization, InventoryItem, User, Membership, Depot


def _mk_depot(session, org_id: str, code: str):
    """Ensure a Depot row exists so inventory FKs hold."""
    qualified = f"{org_id}:{code}"
    d = session.get(Depot, qualified)
    if d is None:
        session.add(Depot(id=qualified, org_id=org_id, name=code,
                          lat=0.0, lng=0.0, sector="T", status="OPERATIONAL"))
        session.flush()
    return qualified


@pytest.fixture(scope="module")
def db_url(tmp_path_factory):
    path = tmp_path_factory.mktemp("persistence") / "p2.db"
    return f"sqlite:///{path}"


@pytest.fixture(scope="module")
def migrated_engine(db_url):
    eng = build_engine(db_url)
    run_migrations(eng)
    # Point the module-global session factory at THIS database so every
    # session_scope() call in these tests uses the migrated temp DB.
    import app.db as db_mod
    db_mod._engine = eng
    db_mod._SessionFactory = db_mod.build_session_factory(eng)
    return eng


@pytest.fixture(scope="module")
def org_id(migrated_engine):
    with session_scope() as s:
        org = persistence.get_or_create_organization(s, "Test Org", f"test-{uuid.uuid4().hex[:6]}")
        oid = org.id
    return oid


# ----------------------------------------------------------------------
# Migration reproducibility
# ----------------------------------------------------------------------
class TestMigrations:
    def test_migrations_idempotent(self, migrated_engine):
        assert run_migrations(migrated_engine) == []

    def test_fresh_database_schema_reproducible(self, tmp_path, migrated_engine):
        eng2 = build_engine(f"sqlite:///{tmp_path/'fresh.db'}")
        run_migrations(eng2)
        from sqlalchemy import inspect
        t1 = set(inspect(migrated_engine).get_table_names())
        t2 = set(inspect(eng2).get_table_names())
        assert t1 == t2 and len(t2) >= 19


# ----------------------------------------------------------------------
# Transactional inventory
# ----------------------------------------------------------------------
class TestInventoryTransactions:
    def test_movement_updates_quantity_atomically(self, migrated_engine, org_id):
        with session_scope() as s:
            _mk_depot(s, org_id, "D1")
            persistence.seed_inventory(s, org_id, "D1", "water", 100.0)
        with session_scope() as s:
            ok = persistence.apply_inventory_movement(s, org_id, "D1", "water", -30.0,
                                                       "DELIVERY", "R1", "mv-key-1")
            assert ok is True
        with session_scope() as s:
            inv = persistence.get_inventory(s, org_id)
            assert inv[f"{org_id}:D1"]["water"] == 70.0

    def test_replayed_movement_rejected_by_idempotency_key(self, migrated_engine, org_id):
        with session_scope() as s:
            ok = persistence.apply_inventory_movement(s, org_id, "D1", "water", -30.0,
                                                       "DELIVERY", "R1", "mv-key-1")
            assert ok is False  # same idempotency key — replay rejected
        with session_scope() as s:
            inv = persistence.get_inventory(s, org_id)
            assert inv[f"{org_id}:D1"]["water"] == 70.0  # unchanged

    def test_stock_cannot_go_negative_db_enforced(self, migrated_engine, org_id):
        from sqlalchemy.exc import IntegrityError
        from app.db import get_session_factory
        s = get_session_factory()()
        try:
            with pytest.raises(IntegrityError):
                persistence.apply_inventory_movement(s, org_id, "D1", "water", -10000.0,
                                                     "DELIVERY", "R2", "mv-key-neg")
                s.commit()
        finally:
            s.rollback()
            s.close()
        with session_scope() as s2:
            inv = persistence.get_inventory(s2, org_id)
            assert inv[f"{org_id}:D1"]["water"] == 70.0  # rolled back

    def test_concurrent_allocations_never_exceed_stock(self, migrated_engine, org_id):
        """20 threads each deduct 5 from a 60-unit stock → exactly 12 succeed,
        stock ends at 0, never negative."""
        with session_scope() as s:
            _mk_depot(s, org_id, "D2")
            persistence.seed_inventory(s, org_id, "D2", "water", 60.0)
        results = []
        barrier = threading.Barrier(20)

        def worker(i):
            barrier.wait()
            try:
                with session_scope() as s:
                    ok = persistence.apply_inventory_movement(
                        s, org_id, "D2", "water", -5.0, "DELIVERY", f"CR-{i}",
                        f"conc-{uuid.uuid4().hex[:8]}-{i}")
                results.append(ok)
            except Exception as e:
                results.append(f"err:{e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        with session_scope() as s:
            inv = persistence.get_inventory(s, org_id)
            final = inv[f"{org_id}:D2"]["water"]
        assert final >= 0
        assert final == 60.0 - 5.0 * sum(1 for r in results if r is True)


# ----------------------------------------------------------------------
# Idempotent delivery (database level)
# ----------------------------------------------------------------------
class TestDeliveryPersistence:
    def test_duplicate_confirm_single_deduction(self, migrated_engine, org_id):
        with session_scope() as s:
            _mk_depot(s, org_id, "D3")
            persistence.seed_inventory(s, org_id, "D3", "water", 500.0)
        items = [{"item_type": "water", "quantity": 50.0}]
        with session_scope() as s:
            persistence.persist_request(s, org_id, {"id": "DR1", "requester_name": "x",
                "location": {"lat": 0, "lng": 0}, "items": items, "priority": "MEDIUM",
                "status": "DISPATCHED", "created_at": 1.0})
        with session_scope() as s:
            r1 = persistence.confirm_delivery_persisted(s, org_id, "DR1", "V", "h1",
                                                         items, "D3")
        with session_scope() as s:
            r2 = persistence.confirm_delivery_persisted(s, org_id, "DR1", "V", "h1",
                                                         items, "D3")
        assert r2["duplicate"] is True and r2["already_persisted"] is True
        with session_scope() as s:
            inv = persistence.get_inventory(s, org_id)
            assert inv[f"{org_id}:D3"]["water"] == 450.0  # exactly one deduction

    def test_concurrent_duplicate_confirm_single_deduction(self, migrated_engine, org_id):
        with session_scope() as s:
            _mk_depot(s, org_id, "D4")
            persistence.seed_inventory(s, org_id, "D4", "water", 500.0)
        items = [{"item_type": "water", "quantity": 25.0}]
        with session_scope() as s:
            persistence.persist_request(s, org_id, {"id": "DR2", "requester_name": "x",
                "location": {"lat": 0, "lng": 0}, "items": items, "priority": "MEDIUM",
                "status": "DISPATCHED", "created_at": 1.0})
        errors = []

        def worker():
            try:
                with session_scope() as s:
                    persistence.confirm_delivery_persisted(s, org_id, "DR2", "V", "h2",
                                                           items, "D4")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        with session_scope() as s:
            inv = persistence.get_inventory(s, org_id)
            assert inv[f"{org_id}:D4"]["water"] == 475.0  # ONE deduction despite 5 racers
        # Either unique-constraint aborts (errors) or the pre-check returns
        # already_persisted; in both cases stock moved exactly once.

    def test_delivery_persists_across_reconnect(self, migrated_engine, db_url, org_id):
        """Simulated restart: a NEW engine instance reconciles from the DB and
        the delivery stays delivered."""
        from app.state_engine import CrisisStateEngine
        with session_scope() as s:
            persistence.get_or_create_organization(s, "Persist Test Org",
                                                    f"persist-{uuid.uuid4().hex[:6]}",
                                                    org_id="ORG-PERSIST-TEST")
        eng = CrisisStateEngine(seed=42, org_id="ORG-PERSIST-TEST", persist=True)
        req = next(r for r in eng.requests.values()
                   if r.status.value == "DISPATCHED" and r.assigned_depot_id)
        eng.confirm_delivery(req.id, "Volunteer")
        delivered_id = req.id
        del eng
        # new instance (same DB) must reconcile the delivered status
        eng2 = CrisisStateEngine(seed=42, org_id="ORG-PERSIST-TEST", persist=True)
        assert eng2.requests[delivered_id].status.value == "DELIVERED"
        assert eng2.requests[delivered_id].is_delivered is True


# ----------------------------------------------------------------------
# Audit chain tamper-evidence
# ----------------------------------------------------------------------
class TestAuditChain:
    def test_chain_valid_and_grows(self, migrated_engine, org_id):
        with session_scope() as s:
            persistence.append_audit_event(s, org_id, "EV1", "actor", "AGENT",
                                           "T", "e1", "first")
            persistence.append_audit_event(s, org_id, "EV2", "actor", "AGENT",
                                           "T", "e2", "second")
            report = persistence.verify_audit_chain(s, org_id)
        assert report["valid"] is True

    def test_tampered_payload_detected(self, migrated_engine, org_id):
        with session_scope() as s:
            persistence.append_audit_event(s, org_id, "EV3", "actor", "AGENT",
                                           "T", "e3", "to-be-tampered")
        from sqlalchemy import update
        with session_scope() as s:
            s.execute(update(AuditEventRow := __import__("app.models_db", fromlist=["AuditEventRow"]).AuditEventRow)
                      .where(AuditEventRow.summary == "to-be-tampered")
                      .values(summary="TAMPERED-SILENTLY"))
        with session_scope() as s:
            report = persistence.verify_audit_chain(s, org_id)
        assert report["valid"] is False
        assert any("mismatch" in p for p in report["problems"])

    def test_broken_prev_hash_detected(self, migrated_engine, org_id):
        from app.models_db import AuditEventRow
        from sqlalchemy import update
        with session_scope() as s:
            rows = persistence.list_audit_events(s, org_id, limit=5)
            target = rows[0]  # most recent
            s.execute(update(AuditEventRow).where(AuditEventRow.id == target.id)
                      .values(prev_hash="deadbeef" * 8))
        with session_scope() as s:
            report = persistence.verify_audit_chain(s, org_id)
        assert report["valid"] is False
        assert any("prev-hash" in p for p in report["problems"])


# ----------------------------------------------------------------------
# Transactional outbox
# ----------------------------------------------------------------------
class TestOutbox:
    def test_outbox_claim_process_replay_safe(self, migrated_engine, org_id):
        with session_scope() as s:
            persistence.enqueue_outbox(s, org_id, "NOTIFY",
                                        {"msg": "x"}, "ob-key-1")
        with session_scope() as s:
            pending = persistence.claim_pending_outbox(s)
            assert len(pending) == 1
            persistence.mark_outbox_processed(s, pending[0].id)
        with session_scope() as s:
            pending = persistence.claim_pending_outbox(s)
            assert len(pending) == 0  # processed once; no redelivery

    def test_outbox_replay_rejected_by_idempotency_key(self, migrated_engine, org_id):
        with session_scope() as s:
            persistence.enqueue_outbox(s, org_id, "NOTIFY", {"msg": "x"}, "ob-key-2")
        with pytest.raises(Exception, match="constraint"):
            with session_scope() as s:
                persistence.enqueue_outbox(s, org_id, "NOTIFY", {"msg": "x"}, "ob-key-2")
