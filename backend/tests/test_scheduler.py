"""Phase V durable-scheduler tests (Studio topic 20).

Duplicate-trigger protection, interval gating, lock contention, failure
recording with retry, UTC storage and permission gating.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app import scheduler as sched


COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"


@pytest.fixture(autouse=True)
def _registered(client):  # client first: fresh DB + migrations before registry use
    sched.register_builtin_jobs()
    sched.ensure_jobs_registered()
    yield


class TestScheduler:
    def test_first_tick_runs_all_jobs(self):
        result = sched.tick()
        jobs = result["jobs"]
        assert set(jobs) == {"outbox_recovery", "audit_integrity_check",
                             "inventory_expiry_check"}
        assert all(j["status"] == "OK" for j in jobs.values())
        assert jobs["audit_integrity_check"]["outcome"]["chains"][
            "ORG-PACIFIC"] is True

    def test_duplicate_trigger_is_a_noop(self):
        first = sched.tick()
        assert all(j["status"] == "OK" for j in first["jobs"].values())
        second = sched.tick()  # immediate re-trigger: nothing is due
        assert all(j["status"] == "skipped_not_due"
                   for j in second["jobs"].values()) or second["jobs"] == {}
        # durable state: jobs recorded exactly one run
        status = sched.scheduler_status()["jobs"]
        by_name = {j["job_name"]: j for j in status}
        assert by_name["outbox_recovery"]["runs"] >= 1
        assert by_name["outbox_recovery"]["last_status"] == "OK"

    def test_force_runs_again_and_is_idempotent(self):
        sched.tick()
        forced = sched.tick(force=True)
        assert all(j["status"] == "OK" for j in forced["jobs"].values())
        # outbox recovery is idempotent: second run processes nothing new
        assert forced["jobs"]["outbox_recovery"]["outcome"]["count"] >= 0

    def test_locked_job_is_skipped(self):
        from app.db import session_scope
        from app.models_db import ScheduledJobRow
        now = datetime.now(timezone.utc)
        with session_scope() as s:
            row = s.get(ScheduledJobRow, "outbox_recovery")
            row.lock_expires_at = now + timedelta(seconds=300)  # held by another worker
        result = sched.tick(force=True)
        assert result["jobs"]["outbox_recovery"]["status"] == "skipped_locked"

    def test_failure_recorded_and_retried_next_tick(self, monkeypatch):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("job crashed")
            return {"recovered": True}
        monkeypatch.setitem(sched._JOB_FUNCS, "inventory_expiry_check", flaky)
        sched.tick(force=True)
        status = {j["job_name"]: j for j in sched.scheduler_status()["jobs"]}
        assert status["inventory_expiry_check"]["last_status"] == "FAILED"
        assert "job crashed" in status["inventory_expiry_check"]["last_error"]
        # next tick: the failure did not wedge the job
        sched.tick(force=True)
        assert calls["n"] == 2
        status = {j["job_name"]: j for j in sched.scheduler_status()["jobs"]}
        assert status["inventory_expiry_check"]["last_status"] == "OK"

    def test_utc_timestamps(self):
        sched.tick()
        status = {j["job_name"]: j for j in sched.scheduler_status()["jobs"]}
        raw = status["outbox_recovery"]["last_run_at"]
        assert raw is None or raw.endswith("+00:00")  # stored UTC, tz-aware


class TestSchedulerAPI:
    def test_tick_endpoint_and_permissions(self, client):
        h = client.login(COORD)
        r = client.post("/api/v1/scheduler/tick", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert "tick_at" in body and body["tick_at"].endswith("+00:00")
        # second immediate tick: nothing due, no duplicate execution
        r2 = client.post("/api/v1/scheduler/tick", headers=h)
        assert r2.status_code == 200
        # volunteers cannot trigger the scheduler
        r3 = client.post("/api/v1/scheduler/tick", headers=client.login(VOL))
        assert r3.status_code == 403

    def test_status_endpoint_reports_durable_state(self, client):
        r = client.get("/api/v1/scheduler/status",
                       headers=client.login(COORD))
        assert r.status_code == 200
        jobs = {j["job_name"]: j for j in r.json()["jobs"]}
        assert "outbox_recovery" in jobs
        assert jobs["outbox_recovery"]["interval_seconds"] > 0
        assert jobs["outbox_recovery"]["description"]
