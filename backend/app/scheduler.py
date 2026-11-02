"""Phase V durable scheduler (System Design Studio topic 20).

DB-backed scheduled jobs with atomic claiming: a job row is claimed under a
row lock, so two concurrent ticks (or two replicas) can NEVER both execute
the same job — the duplicate trigger is a no-op. All instants are UTC.
Jobs are idempotent by contract; a failed run is recorded and retried on the
next due tick. Nothing is claimed to have run unless a durable row says so.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

from sqlalchemy import select, update

from .db import session_scope
from .models_db import ScheduledJobRow


def _now():
    return datetime.now(timezone.utc)


# Job registry: name -> (interval_seconds, callable). Callables must be
# idempotent and side-effect-safe (durable outcomes only).
JOBS: Dict[str, Dict[str, Any]] = {
    "outbox_recovery": {
        "interval_seconds": 60,
        "description": "Dispatch pending transactional-outbox events "
                       "(idempotent consumer with dead-letter).",
    },
    "audit_integrity_check": {
        "interval_seconds": 3600,
        "description": "Verify the hash chain of every organization's audit log.",
    },
    "inventory_expiry_check": {
        "interval_seconds": 3600,
        "description": "Count stock lines expiring within 30 days per org.",
    },
}

# Resolved at registration to avoid import cycles
_JOB_FUNCS: Dict[str, Callable[[], Dict[str, Any]]] = {}


def register_builtin_jobs():
    if _JOB_FUNCS:
        return
    from . import persistence_phase4
    from . import persistence_phase3
    from . import persistence

    def outbox_recovery() -> Dict[str, Any]:
        return persistence_phase4.dispatch_outbox(limit=50)

    def audit_integrity_check() -> Dict[str, Any]:
        results = {}
        with session_scope() as session:
            from .models_db import Organization
            orgs = session.execute(select(Organization.id)).scalars().all()
            for org_id in orgs:
                report = persistence.verify_audit_chain(session, org_id)
                results[org_id] = report.get("valid", False)
        return {"chains": results}

    def inventory_expiry_check() -> Dict[str, Any]:
        from .models_db import Organization
        counts = {}
        with session_scope() as session:
            orgs = session.execute(select(Organization.id)).scalars().all()
            for org_id in orgs:
                items = persistence_phase3.expiring_inventory(org_id, within_days=30)
                counts[org_id] = len(items)
        return {"expiring_by_org": counts}

    _JOB_FUNCS["outbox_recovery"] = outbox_recovery
    _JOB_FUNCS["audit_integrity_check"] = audit_integrity_check
    _JOB_FUNCS["inventory_expiry_check"] = inventory_expiry_check


def ensure_jobs_registered():
    with session_scope() as session:
        for name, spec in JOBS.items():
            row = session.get(ScheduledJobRow, name)
            if row is None:
                session.add(ScheduledJobRow(job_name=name,
                                           interval_seconds=spec["interval_seconds"]))
        session.flush()


def _aware(dt):
    """SQLite returns naive datetimes; treat stored values as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def claim_job(session, name: str, now, lease_s: int = 120):
    """Atomic conditional claim. Returns the NEW fencing token, or None when another
    holder's unexpired lease exists. The fence strictly increases on every claim, so any
    holder with an older token can be recognised and rejected at write time."""
    res = session.execute(
        update(ScheduledJobRow)
        .where(ScheduledJobRow.job_name == name,
               (ScheduledJobRow.lock_expires_at.is_(None)) | (ScheduledJobRow.lock_expires_at <= now))
        .values(lock_token=uuid.uuid4().hex[:12], fence=ScheduledJobRow.fence + 1,
                lock_expires_at=now + timedelta(seconds=lease_s)))
    if res.rowcount == 0:
        return None
    return session.execute(select(ScheduledJobRow.fence).where(ScheduledJobRow.job_name == name)).scalar_one()


def finish_job_in(session, name: str, fence: int, status: str, error, now) -> bool:
    """Fenced completion write: applies only while the job's fence still equals the token
    issued at claim time. If the lease expired and another worker re-claimed the job
    (fence bumped), this stale holder's write is REJECTED (rowcount 0): it can neither
    overwrite newer state nor release the new holder's lease. Returns True when applied."""
    values = dict(last_status=status, last_error=error, lock_token=None, lock_expires_at=None)
    if status == "OK":
        values.update(last_run_at=now, runs=ScheduledJobRow.runs + 1)
    res = session.execute(update(ScheduledJobRow)
                          .where(ScheduledJobRow.job_name == name, ScheduledJobRow.fence == fence)
                          .values(**values))
    return res.rowcount == 1


def finish_job(name: str, fence: int, status: str, error, now) -> bool:
    with session_scope() as session:
        return finish_job_in(session, name, fence, status, error, now)


def tick(force: bool = False, now: datetime = None) -> Dict[str, Any]:
    """Runs all due jobs. Phase 1 atomically claims due jobs (duplicate or
    concurrent ticks get rowcount 0 → no-op); phase 2 executes each claimed
    job outside the claim transaction and records the durable outcome."""
    register_builtin_jobs()
    now = _aware(now or _now())
    executed: Dict[str, Any] = {}

    # Phase 1: claim due jobs in one short write transaction
    claimed: list[tuple] = []   # (job_name, fencing token issued with the claim)
    with session_scope() as session:
        rows = session.execute(select(ScheduledJobRow)).scalars().all()
        for row in rows:
            spec = JOBS.get(row.job_name)
            if not spec:
                continue
            last_run = _aware(row.last_run_at)
            lock_exp = _aware(row.lock_expires_at)
            due = force or (last_run is None
                            or (now - last_run).total_seconds() >= row.interval_seconds)
            if not due:
                executed[row.job_name] = {"status": "skipped_not_due"}
                continue
            if lock_exp is not None and lock_exp > now:
                executed[row.job_name] = {"status": "skipped_locked"}
                continue
            fence = claim_job(session, row.job_name, now)
            if fence is None:
                executed[row.job_name] = {"status": "skipped_contended"}
            else:
                claimed.append((row.job_name, fence))
        session.flush()

    # Phase 2: execute each claimed job, then record the durable outcome
    for name, fence in claimed:
        try:
            outcome = _JOB_FUNCS[name]()
            ok = finish_job(name, fence, "OK", None, now)
            executed[name] = ({"status": "OK", "outcome": outcome} if ok
                              else {"status": "stale_holder_rejected", "fence": fence})
        except Exception as e:  # noqa: BLE001 — durable failure record
            ok = finish_job(name, fence, "FAILED", str(e)[:500], now)
            executed[name] = ({"status": "FAILED", "error": str(e)} if ok
                              else {"status": "stale_holder_rejected", "fence": fence})
    return {"tick_at": now.isoformat(), "jobs": executed}


def scheduler_status() -> Dict[str, Any]:
    ensure_jobs_registered()
    with session_scope() as session:
        rows = session.execute(select(ScheduledJobRow)).scalars().all()
        return {"jobs": [{
            "job_name": r.job_name,
            "interval_seconds": r.interval_seconds,
            "last_run_at": (_aware(r.last_run_at).isoformat()
                            if r.last_run_at else None),
            "last_status": r.last_status,
            "last_error": r.last_error,
            "runs": r.runs,
            "description": JOBS.get(r.job_name, {}).get("description", ""),
        } for r in rows]}
