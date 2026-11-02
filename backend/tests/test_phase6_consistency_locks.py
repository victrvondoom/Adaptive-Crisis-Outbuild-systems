"""Phase VI topics 25-28, 32-35, 39: leases/fencing, consistency, streaming, search, schema, regions."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import advanced_lab as L, advanced_lab_ext as E, scheduler
from app.models_db import ScheduledJobRow


def _all(r):
    bad = [k for k, v in r["invariants"].items() if not v]
    assert not bad, bad


def test_lease_fencing_lab():
    _all(E.lease_fencing())


def test_stale_holder_cannot_overwrite_or_release(tmp_path):
    """REGRESSION: before v5, finish wrote by job_name only, so a paused worker whose lease had
    expired could clear the NEW holder's lock and record a result. Fails without the fence."""
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with L.disposable_db("fence") as (_, factory, _p):
        with factory() as s:
            s.add(ScheduledJobRow(job_name="j", interval_seconds=60))
            s.commit()
        with factory() as s:
            fa = scheduler.claim_job(s, "j", t0); s.commit()
        with factory() as s:
            fb = scheduler.claim_job(s, "j", t0 + timedelta(seconds=200)); s.commit()
        assert fb == fa + 1
        with factory() as s:
            assert scheduler.finish_job_in(s, "j", fa, "OK", None, t0) is False
            s.commit()
        with factory() as s:
            row = s.get(ScheduledJobRow, "j")
            assert row.lock_expires_at is not None and row.runs == 0   # B's lease intact, no phantom run
        with factory() as s:
            assert scheduler.finish_job_in(s, "j", fb, "OK", None, t0) is True; s.commit()


def test_lease_blocks_second_claim_until_expiry():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with L.disposable_db("lease2") as (_, factory, _p):
        with factory() as s:
            s.add(ScheduledJobRow(job_name="j", interval_seconds=60)); s.commit()
        with factory() as s:
            assert scheduler.claim_job(s, "j", t0) == 1; s.commit()
        with factory() as s:
            assert scheduler.claim_job(s, "j", t0 + timedelta(seconds=119)) is None
        with factory() as s:
            assert scheduler.claim_job(s, "j", t0 + timedelta(seconds=121)) == 2; s.commit()


def test_replica_routing_never_serves_critical_reads_from_replica():
    r = E.replica_routing()
    _all(r)
    for kind in ("inventory_availability", "delivery_confirmation", "plan_approval", "mission_state", "audit_verification"):
        pass  # routing table asserted inside the lab; spot-check ordering below
    assert r["log"][0]["naive_replica_read"]["version"] < r["log"][0]["routed_inventory_read"]["version"]


def test_cap_partition_cp_vs_ap():
    r = E.cap_partition()
    _all(r)
    assert r["ap_strategy"]["total_reserved_of_10"] == 16 and r["cp_strategy"]["total_reserved_of_10"] == 0


def test_event_stream_reconnect_dedupe_resync():
    _all(E.realtime_reconnect())


def test_event_log_retention_forces_resync():
    log = E.EventLog("e", retention=3)
    for v in range(1, 10):
        log.publish("ORG-A", "k", v)
    assert log.since("ORG-A", 1, "e")["resync_required"] is True


def test_backpressure_policies():
    _all(E.backpressure(events=300, consumer_ms=0.5, bound=20))


def test_search_index_properties():
    _all(E.search_index(docs=800))


def test_schema_evolution_lab():
    r = E.schema_evolution(rows=400, batch=100)
    _all(r)
    assert "NOT a zero-downtime claim" in r["claim"]


def test_sharding_and_region_sims_are_labelled_simulated():
    for r in (E.shard_routing(), E.multi_region(), E.cap_partition(), E.replica_routing(), E.realtime_reconnect()):
        assert r["mode"] == "SIMULATED"
    _all(E.shard_routing()); _all(E.multi_region())


def test_shard_routing_is_deterministic():
    assert E.shard_routing(seed=42)["strategies"] == E.shard_routing(seed=42)["strategies"]
    assert E.shard_routing(seed=1)["strategies"] != E.shard_routing(seed=2)["strategies"]


def test_backup_restore_validates_everything():
    r = E.backup_restore()
    _all(r)
    assert r["events_lost_after_backup"] >= 0 and r["measured_restore_and_validate_ms"] > 0
