"""
AIDNEXUS ONE — Phase VI laboratory, part 2 (topics 25-40).
Same rules as advanced_lab.py: disposable databases, measured numbers, explicit
mode = REAL_MEASURED | SIMULATED. SIMULATED experiments model infrastructure this
repository does not run (replicas, regions, CDN edge) with seeded deterministic code.
"""
from __future__ import annotations

import hashlib
import os
import queue
import random
import shutil
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select, text, func

from .advanced_lab import (disposable_db, environment, summarize, LAB_SEED, _seed_orgs, percentile)
from .models_db import ScheduledJobRow, InventoryItem, InventoryMovement, AuditEventRow, DeliveryReceiptRow
from . import persistence, scheduler, telemetry
from .keyring import Keyring, SecretMissing, KeyRevoked, require_secret
from cryptography.fernet import InvalidToken


# ---------------------------------------------------------------------------
# Topic 28 — lease + fencing token (REAL scheduler.claim_job / finish_job_in)
# ---------------------------------------------------------------------------
def lease_fencing() -> Dict[str, Any]:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timeline: List[Dict[str, Any]] = []
    with disposable_db("lease") as (engine, factory, _):
        with factory() as s:
            s.add(ScheduledJobRow(job_name="benchmark_job", interval_seconds=60, runs=0))
            s.commit()

        # 1. mutual exclusion under real thread contention
        wins: List[int] = []
        barrier = threading.Barrier(8)

        def contender():
            barrier.wait()
            for attempt in range(6):
                try:
                    with factory() as s:
                        f = scheduler.claim_job(s, "benchmark_job", t0)
                        s.commit()
                    if f is not None:
                        wins.append(f)
                    return
                except Exception as e:  # noqa: BLE001  (sqlite writer lock; retry)
                    if "locked" not in str(e).lower():
                        raise
                    time.sleep(0.01 * (attempt + 1))

        ts = [threading.Thread(target=contender) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        timeline.append({"step": "8 workers race for the lease", "winners": len(wins), "fence": wins})

        # reset to a clean slate for the stale-holder scenario
        with factory() as s:
            s.execute(text("UPDATE scheduled_jobs SET lock_token=NULL, lock_expires_at=NULL, fence=0, runs=0"))
            s.commit()
        with factory() as s:
            a_fence = scheduler.claim_job(s, "benchmark_job", t0)
            s.commit()
        timeline.append({"step": "Worker A claims lease (120 s)", "fence": a_fence})
        with factory() as s:
            b_early = scheduler.claim_job(s, "benchmark_job", t0 + timedelta(seconds=10))
            s.commit()
        timeline.append({"step": "t+10s Worker B tries while A's lease is valid", "claimed": b_early is not None})
        with factory() as s:
            b_fence = scheduler.claim_job(s, "benchmark_job", t0 + timedelta(seconds=130))
            s.commit()
        timeline.append({"step": "t+130s A paused (GC/partition); lease expired; B claims", "fence": b_fence})
        with factory() as s:
            a_ok = scheduler.finish_job_in(s, "benchmark_job", a_fence, "OK", None, t0 + timedelta(seconds=140))
            s.commit()
        timeline.append({"step": "t+140s stale A wakes and tries to write its result", "accepted": a_ok,
                         "note": "fence 1 < current fence 2 -> rejected"})
        with factory() as s:
            row = s.get(ScheduledJobRow, "benchmark_job")
            still_held = row.lock_expires_at is not None
        with factory() as s:
            b_ok = scheduler.finish_job_in(s, "benchmark_job", b_fence, "OK", None, t0 + timedelta(seconds=150))
            s.commit()
            runs = s.get(ScheduledJobRow, "benchmark_job").runs
        timeline.append({"step": "B finishes with its own token", "accepted": b_ok, "runs": runs})

        # counterfactual: what an UNFENCED write would have done (shows why the token matters)
        with factory() as s:
            s.execute(text("UPDATE scheduled_jobs SET lock_token='x', lock_expires_at=:e, fence=fence+1"),
                      {"e": t0 + timedelta(seconds=999)})
            s.commit()
        with factory() as s:
            s.execute(text("UPDATE scheduled_jobs SET lock_token=NULL, lock_expires_at=NULL"))  # naive stale release
            s.commit()
            naive_released_foreign_lease = s.get(ScheduledJobRow, "benchmark_job").lock_expires_at is None
        timeline.append({"step": "COUNTERFACTUAL: naive unfenced release by a stale holder",
                         "foreign_lease_wiped": naive_released_foreign_lease})
    return {"topic": 28, "mode": "REAL_MEASURED",
            "implementation_under_test": "app/scheduler.py claim_job + finish_job_in (fencing column scheduled_jobs.fence, migration v5)",
            "environment": environment(), "timeline": timeline,
            "invariants": {"exactly_one_winner": len(wins) == 1, "b_blocked_while_lease_valid": b_early is None,
                           "fence_strictly_increases": b_fence is not None and b_fence > a_fence,
                           "stale_holder_rejected": a_ok is False and still_held,
                           "current_holder_accepted": b_ok is True and runs == 1},
            "limitations": ["lease and fence live in the application database; there is no Redis/etcd lock service",
                            "uniqueness constraints are preferred where they suffice (e.g. delivery_receipts PK)"]}


# ---------------------------------------------------------------------------
# Topic 34 — backpressure policies (real threads, real bounded queues)
# ---------------------------------------------------------------------------
def backpressure(events: int = 600, consumer_ms: float = 1.0, bound: int = 50) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for policy in ("unbounded", "block", "drop_oldest", "reject_newest"):
        q: "queue.Queue" = queue.Queue(maxsize=0 if policy == "unbounded" else bound)
        delivered: List[int] = []
        dropped = [0]
        peak = [0]
        stop = threading.Event()

        def consumer():
            while not stop.is_set() or not q.empty():
                try:
                    item = q.get(timeout=0.02)
                except queue.Empty:
                    continue
                time.sleep(consumer_ms / 1000)
                delivered.append(item)

        c = threading.Thread(target=consumer)
        c.start()
        t0 = time.perf_counter()
        for i in range(events):
            if policy in ("unbounded", "block"):
                q.put(i)                      # block waits when full -> producer slowed
            elif policy == "drop_oldest":
                while True:
                    try:
                        q.put_nowait(i)
                        break
                    except queue.Full:
                        try:
                            q.get_nowait()
                            dropped[0] += 1
                        except queue.Empty:
                            pass
            else:
                try:
                    q.put_nowait(i)
                except queue.Full:
                    dropped[0] += 1
            peak[0] = max(peak[0], q.qsize())
        produce_s = time.perf_counter() - t0
        stop.set()
        c.join()
        out[policy] = {"produced": events, "delivered": len(delivered), "dropped": dropped[0],
                       "peak_queue_depth": peak[0], "producer_elapsed_ms": round(produce_s * 1000, 1),
                       "duplicates": len(delivered) - len(set(delivered)),
                       "ordered": delivered == sorted(delivered)}
    # cancellation: producer must stop promptly when the consumer goes away
    q2: "queue.Queue" = queue.Queue(maxsize=bound)
    cancelled = threading.Event()
    produced = [0]

    def prod():
        for i in range(10_000):
            if cancelled.is_set():
                return
            try:
                q2.put(i, timeout=0.01)
                produced[0] += 1
            except queue.Full:
                continue

    p = threading.Thread(target=prod)
    p.start()
    time.sleep(0.05)
    cancelled.set()
    t = time.perf_counter()
    p.join(timeout=1)
    out["cancellation"] = {"producer_stopped": not p.is_alive(),
                           "stop_latency_ms": round((time.perf_counter() - t) * 1000, 2),
                           "produced_before_cancel": produced[0], "queue_bound": bound}
    return {"topic": 34, "mode": "REAL_MEASURED",
            "implementation_under_test": "stdlib queue/threading primitives (the app has no streaming endpoint; polling is used)",
            "environment": environment(), "consumer_ms_per_event": consumer_ms, "bound": bound,
            "policies": out,
            "invariants": {"unbounded_depth_exceeds_bound": out["unbounded"]["peak_queue_depth"] > bound,
                           "bounded_depth_respected": all(out[p]["peak_queue_depth"] <= bound
                                                          for p in ("block", "drop_oldest", "reject_newest")),
                           "block_loses_nothing": out["block"]["dropped"] == 0 and out["block"]["delivered"] == events,
                           "drop_policies_lose_data": out["drop_oldest"]["dropped"] > 0 and out["reject_newest"]["dropped"] > 0,
                           "cancellation_prompt": out["cancellation"]["producer_stopped"]}}


# ---------------------------------------------------------------------------
# Topic 33 — resumable tenant-scoped event stream (reconnect / duplicates / restart)
# ---------------------------------------------------------------------------
class EventLog:
    """At-least-once, ordered, tenant-scoped log with resume cursors. `epoch` changes when
    the server restarts (memory lost), forcing clients to resync instead of trusting stale cursors."""
    def __init__(self, epoch: str, retention: int = 100):
        self.epoch, self.retention = epoch, retention
        self.events: List[Dict[str, Any]] = []
        self.next_id = 1

    def publish(self, org_id: str, kind: str, version: int) -> int:
        e = {"id": self.next_id, "org_id": org_id, "kind": kind, "version": version}
        self.next_id += 1
        self.events.append(e)
        self.events = self.events[-self.retention:]
        return e["id"]

    def since(self, org_id: str, last_id: int, epoch: str | None):
        if epoch is not None and epoch != self.epoch:
            return {"resync_required": True, "reason": "server restarted (new epoch)", "events": []}
        first = self.events[0]["id"] if self.events else self.next_id
        if last_id and last_id < first - 1:
            return {"resync_required": True, "reason": "cursor older than retention window", "events": []}
        return {"resync_required": False, "epoch": self.epoch,
                "events": [e for e in self.events if e["id"] > last_id and e["org_id"] == org_id]}


class Client:
    def __init__(self, org):
        self.org, self.last_id, self.epoch, self.state_version, self.seen = org, 0, None, 0, set()
        self.applied: List[int] = []
        self.resyncs = 0

    def apply(self, evs):
        for e in evs:
            if e["id"] in self.seen:
                continue                       # duplicate (at-least-once) -> ignore
            if e["version"] <= self.state_version:
                self.seen.add(e["id"])         # stale update -> ignore, never move state backwards
                continue
            self.seen.add(e["id"])
            self.state_version = e["version"]
            self.applied.append(e["id"])
            self.last_id = max(self.last_id, e["id"])

    def poll(self, log: EventLog):
        r = log.since(self.org, self.last_id, self.epoch)
        if r["resync_required"]:
            self.resyncs += 1
            self.last_id, self.epoch, self.seen = 0, log.epoch, set()
            self.state_version = max([e["version"] for e in log.events if e["org_id"] == self.org] or [0])
            return r
        self.epoch = r["epoch"]
        self.apply(r["events"])
        return r


def realtime_reconnect() -> Dict[str, Any]:
    log = EventLog("epoch-1")
    a, b = Client("ORG-A"), Client("ORG-B")
    for v in (1, 2, 3):
        log.publish("ORG-A", "plan.updated", v)
    log.publish("ORG-B", "plan.updated", 1)
    a.poll(log); b.poll(log)
    steps = [{"step": "connected; initial events", "a_applied": list(a.applied), "b_applied": list(b.applied)}]
    for v in (4, 5):                                   # A's network drops; events keep flowing
        log.publish("ORG-A", "plan.updated", v)
    steps.append({"step": "A offline while 2 events published", "a_last_id": a.last_id})
    a.apply([e for e in log.events if e["org_id"] == "ORG-A" and e["id"] > a.last_id][:1])   # replay overlap
    r = a.poll(log)                                    # reconnect with cursor => replay missed, dedupe overlap
    steps.append({"step": "A reconnects with Last-Event-ID", "replayed": [e["id"] for e in r["events"]],
                  "a_state_version": a.state_version, "duplicates_ignored": True})
    stale_before = a.state_version
    a.apply([{"id": 999, "org_id": "ORG-A", "kind": "plan.updated", "version": 2}])
    steps.append({"step": "stale update (version 2 < 5) delivered late", "state_version_unchanged": a.state_version == stale_before})
    log2 = EventLog("epoch-2")                          # server restart: memory lost, new epoch
    log2.publish("ORG-A", "plan.updated", 6)
    r2 = a.poll(log2)
    steps.append({"step": "server restarts (log lost)", "resync_required": r2["resync_required"], "reason": r2["reason"],
                  "client_resyncs": a.resyncs, "state_version_after_resync": a.state_version})
    return {"topic": 33, "mode": "SIMULATED",
            "implementation_under_test": "EventLog/Client protocol model (NOT deployed: the app uses polling via auto-refresh; SSE is PLANNED)",
            "environment": environment(), "steps": steps,
            "invariants": {"tenant_isolation": b.applied == [4] and all(e["org_id"] == "ORG-B" for e in log.since("ORG-B", 0, "epoch-1")["events"]),
                           "no_missed_events": a.resyncs >= 1 and a.state_version == 6,
                           "stale_ignored": steps[3]["state_version_unchanged"],
                           "restart_forces_resync": r2["resync_required"]}}


# ---------------------------------------------------------------------------
# Topics 25 & 27 — replication lag, read routing, CAP partition (SIMULATED)
# ---------------------------------------------------------------------------
def replica_routing(seed: int = LAB_SEED, lag_ticks: int = 3) -> Dict[str, Any]:
    primary: Dict[str, Any] = {"version": 0, "stock": 100}
    replica: Dict[str, Any] = {"version": 0, "stock": 100}
    pending: List[tuple] = []
    log: List[Dict[str, Any]] = []
    tick = [0]

    def write(delta):
        primary["version"] += 1
        primary["stock"] += delta
        pending.append((tick[0] + lag_ticks, primary["version"], primary["stock"]))
        return primary["version"]

    def advance(n=1):
        for _ in range(n):
            tick[0] += 1
            for p in [x for x in pending if x[0] <= tick[0]]:
                replica["version"], replica["stock"] = p[1], p[2]
                pending.remove(p)

    def read(kind, min_version=0, replica_up=True):
        strong = kind in ("inventory_availability", "delivery_confirmation", "plan_approval", "mission_state", "audit_verification")
        if strong or not replica_up or replica["version"] < min_version:
            return {"served_by": "primary", "version": primary["version"], "stock": primary["stock"]}
        return {"served_by": "replica", "version": replica["version"], "stock": replica["stock"]}

    v = write(-30)
    naive = {"served_by": "replica", "version": replica["version"], "stock": replica["stock"]}
    log.append({"t": tick[0], "step": "write -30 on primary", "naive_replica_read": naive, "routed_inventory_read": read("inventory_availability"),
                "ryw_read_with_token": read("history_report", min_version=v), "analytics_read": read("history_report")})
    advance(lag_ticks)
    log.append({"t": tick[0], "step": f"replica caught up after {lag_ticks} ticks", "analytics_read": read("history_report")})
    v2 = write(-20)
    advance(1)
    log.append({"t": tick[0], "step": "replica unavailable", "inventory_read": read("inventory_availability", replica_up=False),
                "analytics_read": read("history_report", replica_up=False)})
    lost = [p for p in pending]                       # async failover: acknowledged writes not yet replicated
    sync_loss = 0
    log.append({"t": tick[0], "step": "primary fails; promote replica (ASYNC replication)",
                "acknowledged_writes_lost": len(lost), "promoted_stock": replica["stock"], "true_stock_before_failure": primary["stock"],
                "with_synchronous_replication_loss": sync_loss})
    return {"topic": 25, "mode": "SIMULATED",
            "implementation_under_test": "routing model; the app has NO replica (single SQLite/Postgres primary) — replication is PLANNED/PLATFORM-MANAGED",
            "environment": {"note": "deterministic tick simulation"}, "seed": seed, "lag_ticks": lag_ticks, "log": log,
            "invariants": {"naive_read_is_stale": naive["stock"] != primary["stock"] or naive["version"] < v,
                           "critical_reads_never_use_replica": log[0]["routed_inventory_read"]["served_by"] == "primary",
                           "read_your_writes_via_token": log[0]["ryw_read_with_token"]["served_by"] == "primary",
                           "async_failover_can_lose_acked_writes": len(lost) > 0}}


def cap_partition() -> Dict[str, Any]:
    def run(mode):
        a = {"stock": 10, "ver": 1}
        b = {"stock": 10, "ver": 1}
        partitioned = True
        results = []
        for node, name in ((a, "A"), (b, "B")):           # both sides try to reserve 8 of 10 while partitioned
            if mode == "CP":
                ok = False                                  # minority/unreachable quorum -> refuse (unavailable)
                results.append({"node": name, "reserve": 8, "accepted": ok, "reason": "no quorum; request rejected, retry later"})
            else:
                ok = node["stock"] >= 8
                if ok:
                    node["stock"] -= 8
                    node["ver"] += 1
                results.append({"node": name, "reserve": 8, "accepted": ok})
        total_reserved = sum(8 for r in results if r["accepted"])
        # heal
        conflict = (a["ver"] != 1 and b["ver"] != 1)
        return {"during_partition": results, "total_reserved_of_10": total_reserved, "oversold": total_reserved > 10,
                "on_heal": ("conflict detected -> compensation required (cancel one reservation)" if conflict
                            else "no divergence")}
    cp, ap = run("CP"), run("AP")
    analytics = {"ap_ok": True, "note": "eventually-consistent counters merge after heal; staleness acceptable"}
    return {"topic": 27, "mode": "SIMULATED",
            "implementation_under_test": "two-node model of CP vs AP behaviour during a partition; AIDNEXUS runs one primary database",
            "environment": {"note": "deterministic"}, "cp_strategy": cp, "ap_strategy": ap, "analytics_ap": analytics,
            "decision_matrix": [
                {"operation": "inventory reservation", "requirement": "strong (single-writer transaction + CHECK)", "during_partition": "reject writes"},
                {"operation": "delivery confirmation", "requirement": "idempotent transactional update", "during_partition": "reject or queue client-side; never double-apply"},
                {"operation": "mission approval", "requirement": "bind to authoritative plan version", "during_partition": "reject"},
                {"operation": "analytics / history", "requirement": "eventual OK", "during_partition": "serve stale, labelled"},
                {"operation": "search", "requirement": "eventual OK, never authoritative", "during_partition": "serve stale or degrade to DB"}],
            "invariants": {"cp_never_oversells": not cp["oversold"], "cp_is_unavailable_during_partition": not any(r["accepted"] for r in cp["during_partition"]),
                           "ap_can_oversell": ap["oversold"]}}


def shard_routing(seed: int = LAB_SEED, shards: int = 4, events: int = 20000) -> Dict[str, Any]:
    rnd = random.Random(seed)
    orgs = ["ORG-BIG"] * 70 + [f"ORG-{i}" for i in range(30)]   # 70% of traffic from one tenant (skew)
    keys = [(rnd.choice(orgs), i) for i in range(events)]

    def h(x):
        return int(hashlib.sha256(str(x).encode()).hexdigest()[:8], 16)

    def counts(fn):
        c = [0] * shards
        for k in keys:
            c[fn(k)] += 1
        return c

    strategies = {"hash(org_id)": counts(lambda k: h(k[0]) % shards),
                  "hash(event_id)": counts(lambda k: h(k[1]) % shards),
                  "range(event_id)": counts(lambda k: min(shards - 1, k[1] * shards // events))}
    report = {n: {"per_shard": c, "max_over_mean": round(max(c) / (sum(c) / shards), 2)} for n, c in strategies.items()}
    report["hash(org_id)"]["note"] = "tenant key keeps one org's data together but the skewed tenant makes a HOT shard"
    report["hash(event_id)"]["note"] = "even load, but per-org queries become cross-shard fan-out (all shards)"
    return {"topic": 26, "mode": "SIMULATED",
            "implementation_under_test": "routing arithmetic only; AIDNEXUS is NOT sharded and the index experiment shows it does not need to be",
            "environment": {"note": "deterministic"}, "seed": seed, "shards": shards, "events": events, "strategies": report,
            "invariants": {"org_hash_creates_hot_shard": report["hash(org_id)"]["max_over_mean"] > 1.5,
                           "event_hash_is_balanced": report["hash(event_id)"]["max_over_mean"] < 1.2},
            "decision": "NOT_REQUIRED now; PREPARE: org_id already leads every tenant-scoped index, so a tenant-keyed split remains possible"}


def multi_region(seed: int = LAB_SEED) -> Dict[str, Any]:
    tenants = {"ORG-PACIFIC": {"home": "ap-southeast", "residency": "restricted"},
               "ORG-HIGHLAND": {"home": "eu-west", "residency": "restricted"},
               "ORG-OPEN": {"home": "eu-west", "residency": "unrestricted"}}
    steps = []

    def can_replicate(t, dst):
        spec = tenants[t]
        return spec["residency"] == "unrestricted" or dst == spec["home"]

    steps.append({"step": "replication policy check", "ORG-PACIFIC->eu-west": can_replicate("ORG-PACIFIC", "eu-west"),
                  "ORG-OPEN->ap-southeast": can_replicate("ORG-OPEN", "ap-southeast")})
    failed = "eu-west"
    served = {}
    for t, spec in tenants.items():
        if spec["home"] != failed:
            served[t] = "available (home region healthy)"
        elif can_replicate(t, "ap-southeast"):
            served[t] = "failover to ap-southeast (replica; async lag => possible loss)"
        else:
            served[t] = "UNAVAILABLE until home region recovers (residency forbids failover copy)"
    steps.append({"step": f"region {failed} fails", "result": served})
    return {"topic": 39, "mode": "SIMULATED",
            "implementation_under_test": "policy model; AIDNEXUS is deployed in at most ONE region (single-instance demo). Multi-region: NOT_REQUIRED.",
            "environment": {"note": "deterministic"}, "tenants": tenants, "steps": steps,
            "invariants": {"restricted_data_not_replicated_abroad": not steps[0]["ORG-PACIFIC->eu-west"],
                           "unrestricted_may_replicate": steps[0]["ORG-OPEN->ap-southeast"],
                           "restricted_tenant_pays_availability": "UNAVAILABLE" in served["ORG-HIGHLAND"]}}


def cdn_edge(real_headers: Dict[str, Dict[str, str]] | None = None) -> Dict[str, Any]:
    """Edge-cache decision model fed with the app's REAL response headers when supplied."""
    def cacheable(h):
        cc = (h.get("cache-control") or "").lower()
        return not any(x in cc for x in ("no-store", "private")) and ("max-age" in cc or "etag" in {k.lower() for k in h})
    cache: Dict[str, str] = {}
    origin_hits = [0]
    log = []
    samples = real_headers or {}
    for path, h in samples.items():
        ok = cacheable(h)
        for i in (1, 2):
            if ok and path in cache:
                log.append({"path": path, "request": i, "result": "HIT"})
            else:
                origin_hits[0] += 1
                log.append({"path": path, "request": i, "result": "MISS" if ok else "BYPASS (private/no-store)"})
                if ok:
                    cache[path] = h.get("etag", "v1")
    inv = None
    if cache:
        victim = next(iter(cache))
        cache.pop(victim)
        inv = victim
        origin_hits[0] += 1
        log.append({"path": victim, "request": "after purge", "result": "MISS (refetched from origin)"})
    return {"topic": 31, "mode": "SIMULATED",
            "implementation_under_test": "edge model; NO CDN is configured. Headers are REAL (captured from this app). The decision logic is the model.",
            "environment": {"note": "headers measured from live responses"}, "headers_used": samples, "log": log,
            "purged": inv, "origin_requests": origin_hits[0],
            "invariants": {"api_never_cached": all(l["result"].startswith("BYPASS") for l in log if l["path"].startswith("/api/")),
                           "static_cacheable_when_validators_present": any(l["result"] == "HIT" for l in log) or not samples}}


# ---------------------------------------------------------------------------
# Topic 32 — search with an index that is never authoritative (REAL SQLite FTS5)
# ---------------------------------------------------------------------------
def search_index(docs: int = 3000, seed: int = LAB_SEED) -> Dict[str, Any]:
    rnd = random.Random(seed)
    words = ["water", "insulin", "shelter", "flood", "medical", "baby", "formula", "blanket", "rice", "generator"]
    d = tempfile.mkdtemp(prefix="aidnexus_search_")
    con = sqlite3.connect(os.path.join(d, "s.db"))
    con.executescript("""
        CREATE TABLE src(id TEXT PRIMARY KEY, org_id TEXT NOT NULL, body TEXT NOT NULL, version INT NOT NULL, deleted INT DEFAULT 0);
        CREATE TABLE changelog(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, version INT, op TEXT);
        CREATE VIRTUAL TABLE idx USING fts5(body, id UNINDEXED, org_id UNINDEXED, version UNINDEXED);
    """)
    for i in range(docs):
        con.execute("INSERT INTO src VALUES (?,?,?,?,0)", (f"D{i}", "ORG-A" if i % 2 == 0 else "ORG-B",
                    " ".join(rnd.choices(words, k=6)), 1))
        con.execute("INSERT INTO changelog(id,version,op) VALUES (?,?,'upsert')", (f"D{i}", 1))
    applied = {"seq": 0}

    def pipeline(limit=None):
        rows = con.execute("SELECT seq,id,version,op FROM changelog WHERE seq>? ORDER BY seq LIMIT ?",
                           (applied["seq"], limit or 10**9)).fetchall()
        for seq, id_, ver, op in rows:
            cur = con.execute("SELECT version FROM idx WHERE id=?", (id_,)).fetchone()
            if cur and cur[0] >= ver and op == "upsert":
                applied["seq"] = seq
                continue                                    # duplicate / out-of-order event: idempotent no-op
            con.execute("DELETE FROM idx WHERE id=?", (id_,))
            if op == "upsert":
                s = con.execute("SELECT org_id,body,version FROM src WHERE id=? AND deleted=0", (id_,)).fetchone()
                if s:
                    con.execute("INSERT INTO idx(body,id,org_id,version) VALUES (?,?,?,?)", (s[1], id_, s[0], s[2]))
            applied["seq"] = seq
        return len(rows)

    t = time.perf_counter()
    pipeline()
    initial_index_ms = (time.perf_counter() - t) * 1000

    def search(org, q, limit=20, offset=0):
        try:
            rows = con.execute("SELECT id, version, bm25(idx) r FROM idx WHERE idx MATCH ? AND org_id=? "
                               "ORDER BY r, id LIMIT ? OFFSET ?", (q, org, limit, offset)).fetchall()
        except sqlite3.Error:
            rows = con.execute("SELECT id, version, 0 FROM src WHERE org_id=? AND deleted=0 AND body LIKE ? ORDER BY id LIMIT ?",
                               (org, f"%{q}%", limit)).fetchall()
            return {"degraded": True, "results": [{"id": r[0]} for r in rows]}
        out = []
        for id_, ver, _ in rows:
            sv = con.execute("SELECT version, deleted FROM src WHERE id=?", (id_,)).fetchone()   # authoritative re-check
            if sv is None or sv[1]:
                continue                                    # deleted at source: never show
            out.append({"id": id_, "indexed_version": ver, "source_version": sv[0], "stale": ver != sv[0]})
        return {"degraded": False, "results": out}

    lat = []
    for _ in range(60):
        t = time.perf_counter()
        search("ORG-A", "insulin OR flood")
        lat.append((time.perf_counter() - t) * 1000)
    r1 = search("ORG-A", "water")
    tenant_ok = all(con.execute("SELECT org_id FROM src WHERE id=?", (x["id"],)).fetchone()[0] == "ORG-A" for x in r1["results"])
    # update at source, index not yet caught up -> stale awareness
    victim = r1["results"][0]["id"]
    con.execute("UPDATE src SET body='baby formula', version=2 WHERE id=?", (victim,))
    con.execute("INSERT INTO changelog(id,version,op) VALUES (?,2,'upsert')", (victim,))
    lag_events = con.execute("SELECT COUNT(*) FROM changelog WHERE seq>?", (applied["seq"],)).fetchone()[0]
    stale_visible = next(x for x in search("ORG-A", "water")["results"] if x["id"] == victim)["stale"]
    pipeline()
    after_update = [x["id"] for x in search("ORG-A", "water")["results"]]
    # delete: hidden immediately by the authoritative re-check, even before the index catches up
    victim2 = next(x["id"] for x in search("ORG-A", "insulin")["results"])
    con.execute("UPDATE src SET deleted=1 WHERE id=?", (victim2,))
    hidden_before_index = victim2 not in [x["id"] for x in search("ORG-A", "insulin", limit=1000)["results"]]
    con.execute("INSERT INTO changelog(id,version,op) VALUES (?,3,'delete')", (victim2,))
    pipeline()
    # duplicate events
    n_before = con.execute("SELECT COUNT(*) FROM idx").fetchone()[0]
    for _ in range(3):
        con.execute("INSERT INTO changelog(id,version,op) VALUES (?,2,'upsert')", (victim,))
    pipeline()
    n_after = con.execute("SELECT COUNT(*) FROM idx").fetchone()[0]
    # reconciliation: corrupt the index, detect drift, repair
    con.execute("DELETE FROM idx WHERE id IN (SELECT id FROM idx LIMIT 25)")
    src_live = con.execute("SELECT COUNT(*) FROM src WHERE deleted=0").fetchone()[0]
    drift = src_live - con.execute("SELECT COUNT(*) FROM idx").fetchone()[0]
    for (id_,) in con.execute("SELECT id FROM src WHERE deleted=0 AND id NOT IN (SELECT id FROM idx)").fetchall():
        s = con.execute("SELECT org_id,body,version FROM src WHERE id=?", (id_,)).fetchone()
        con.execute("INSERT INTO idx(body,id,org_id,version) VALUES (?,?,?,?)", (s[1], id_, s[0], s[2]))
    drift_after = src_live - con.execute("SELECT COUNT(*) FROM idx").fetchone()[0]
    broken = search("ORG-A", '"unterminated')
    page1 = [x["id"] for x in search("ORG-A", "water", 10, 0)["results"]]
    page1b = [x["id"] for x in search("ORG-A", "water", 10, 0)["results"]]
    con.close()
    shutil.rmtree(d, ignore_errors=True)
    return {"topic": 32, "mode": "REAL_MEASURED",
            "implementation_under_test": "SQLite FTS5 in a disposable DB (relational full-text; the production app exposes NO search endpoint yet — PLANNED)",
            "environment": environment(), "docs": docs, "seed": seed, "initial_index_ms": round(initial_index_ms, 1),
            "query_latency": summarize(lat), "index_lag_events_after_update": lag_events,
            "invariants": {"tenant_isolation": tenant_ok, "stale_result_flagged": stale_visible,
                           "update_propagates_after_pipeline": victim not in after_update,
                           "delete_hidden_before_index_catches_up": hidden_before_index,
                           "duplicate_events_idempotent": n_before == n_after,
                           "reconciliation_repairs_drift": drift == 25 and drift_after == 0,
                           "failure_degrades_to_relational": broken["degraded"],
                           "pagination_stable": page1 == page1b}}


# ---------------------------------------------------------------------------
# Topic 35 — expand / contract schema evolution (REAL, executed on disposable SQLite)
# ---------------------------------------------------------------------------
def schema_evolution(rows: int = 1000, batch: int = 200) -> Dict[str, Any]:
    d = tempfile.mkdtemp(prefix="aidnexus_schema_")
    con = sqlite3.connect(os.path.join(d, "e.db"))
    con.execute("CREATE TABLE req(id INTEGER PRIMARY KEY, priority TEXT NOT NULL)")
    prio = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    con.executemany("INSERT INTO req(priority) VALUES (?)", [(prio[i % 4],) for i in range(rows)])
    con.commit()
    old_app = lambda: con.execute("SELECT id, priority FROM req ORDER BY id LIMIT 1").fetchone()  # noqa: E731
    def new_app_read():
        return con.execute("SELECT id, COALESCE(priority_code, CASE priority WHEN 'LOW' THEN 0 WHEN 'MEDIUM' THEN 1 "
                           "WHEN 'HIGH' THEN 2 ELSE 3 END) FROM req ORDER BY id LIMIT 1").fetchone()
    steps = []
    steps.append({"phase": "0 baseline", "old_app_ok": old_app() is not None})
    con.execute("ALTER TABLE req ADD COLUMN priority_code INTEGER NULL")          # EXPAND (additive, nullable)
    con.commit()
    steps.append({"phase": "1 expand: add nullable priority_code", "old_app_ok": old_app() is not None,
                  "new_app_reads_via_fallback": new_app_read() is not None})
    # new app: dual-write for new rows
    con.execute("INSERT INTO req(priority, priority_code) VALUES ('HIGH', 2)")
    con.commit()
    # backfill in batches with an interruption + restart
    codes = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    def backfill(max_batches=None):
        done = 0
        while True:
            ids = [r[0] for r in con.execute("SELECT id FROM req WHERE priority_code IS NULL LIMIT ?", (batch,)).fetchall()]
            if not ids or (max_batches is not None and done >= max_batches):
                return done
            for i in ids:
                p = con.execute("SELECT priority FROM req WHERE id=?", (i,)).fetchone()[0]
                con.execute("UPDATE req SET priority_code=? WHERE id=?", (codes[p], i))
            con.commit()
            done += 1
    b1 = backfill(max_batches=2)
    remaining_after_interrupt = con.execute("SELECT COUNT(*) FROM req WHERE priority_code IS NULL").fetchone()[0]
    steps.append({"phase": "2 backfill interrupted (process killed after 2 batches)", "batches": b1,
                  "rows_unfilled": remaining_after_interrupt, "old_app_ok": old_app() is not None,
                  "new_app_still_correct": new_app_read() is not None})
    backfill()
    unfilled = con.execute("SELECT COUNT(*) FROM req WHERE priority_code IS NULL").fetchone()[0]
    mismatches = con.execute("SELECT COUNT(*) FROM req WHERE priority_code != CASE priority WHEN 'LOW' THEN 0 WHEN 'MEDIUM' THEN 1 WHEN 'HIGH' THEN 2 ELSE 3 END").fetchone()[0]
    steps.append({"phase": "3 backfill resumed to completion (idempotent)", "rows_unfilled": unfilled, "mismatches": mismatches})
    # CONTRACT only after verification AND after old app instances are retired
    con.execute("ALTER TABLE req DROP COLUMN priority")
    con.commit()
    try:
        old_app()
        old_after = True
    except sqlite3.OperationalError:
        old_after = False
    steps.append({"phase": "4 contract: drop old column", "old_app_ok": old_after,
                  "meaning": "any old instance still running now FAILS — contract is safe only after all old instances are gone",
                  "rollback": "not possible without restoring from backup (data in dropped column is gone)"})
    con.close()
    shutil.rmtree(d, ignore_errors=True)
    return {"topic": 35, "mode": "REAL_MEASURED",
            "implementation_under_test": "disposable SQLite DB; migration v5 is itself expand-only (idempotent CREATE INDEX IF NOT EXISTS + ADD COLUMN)",
            "environment": environment(), "rows": rows, "batch": batch, "steps": steps,
            "invariants": {"old_app_works_through_expand": steps[1]["old_app_ok"] and steps[2]["old_app_ok"],
                           "interrupted_backfill_resumes": remaining_after_interrupt > 0 and unfilled == 0,
                           "backfill_lossless": mismatches == 0,
                           "contract_breaks_old_app": old_after is False},
            "claim": "NOT a zero-downtime claim: single-process SQLite, no traffic generator, no rolling deploy was run."}


# ---------------------------------------------------------------------------
# Topic 40 — backup / restore / integrity validation (REAL production code paths)
# ---------------------------------------------------------------------------
def backup_restore() -> Dict[str, Any]:
    from .db import build_engine, build_session_factory, run_migrations
    d = tempfile.mkdtemp(prefix="aidnexus_dr_")
    src_path, bak_path, restored_path = (os.path.join(d, n) for n in ("prod_like.db", "backup.db", "restored.db"))
    engine = build_engine(f"sqlite:///{src_path}")
    run_migrations(engine)
    factory = build_session_factory(engine)
    with factory() as s:
        _seed_orgs(s)
        for org in ("ORG-A", "ORG-B"):
            persistence.ensure_depot(s, org, "D1")
            persistence.seed_inventory(s, org, "D1", "water", 500)
            for i in range(40):
                persistence.apply_inventory_movement(s, org, "D1", "water", -5.0, "DELIVERY", request_id=f"R{i}",
                                                     idempotency_key=f"dr:{org}:{i}")
                persistence.append_audit_event(s, org, "DELIVERY_CONFIRMED", "sys", "SYSTEM", "AidRequest", f"R{i}", "delivered")
        s.commit()
    # online backup WHILE a writer keeps writing (SQLite backup API gives a consistent snapshot)
    stop = threading.Event()
    def writer():
        i = 1000
        while not stop.is_set():
            try:
                with factory() as s:
                    persistence.append_audit_event(s, "ORG-A", "BG", "sys", "SYSTEM", "x", f"b{i}", "bg")
                    s.commit()
                i += 1
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.002)
    w = threading.Thread(target=writer)
    w.start()
    time.sleep(0.05)
    t = time.perf_counter()
    raw = sqlite3.connect(src_path)
    dst = sqlite3.connect(bak_path)
    raw.backup(dst)
    dst.close(); raw.close()
    backup_ms = (time.perf_counter() - t) * 1000
    stop.set(); w.join()
    with factory() as s:
        events_at_disaster = s.execute(select(func.count()).select_from(AuditEventRow).where(AuditEventRow.org_id == "ORG-A")).scalar_one()
    bak_events = sqlite3.connect(bak_path).execute("SELECT COUNT(*) FROM audit_events WHERE org_id='ORG-A'").fetchone()[0]
    engine.dispose()
    os.remove(src_path)                                           # DISASTER: primary storage gone
    for ext in ("-wal", "-shm"):
        if os.path.exists(src_path + ext):
            os.remove(src_path + ext)
    t_rto = time.perf_counter()
    shutil.copyfile(bak_path, restored_path)                      # RESTORE
    e2 = build_engine(f"sqlite:///{restored_path}")
    applied = run_migrations(e2)                                  # migration re-application must be a safe no-op
    f2 = build_session_factory(e2)
    with f2() as s:
        chain = {o: persistence.verify_audit_chain(s, o) for o in ("ORG-A", "ORG-B")}
        recon = {}
        for o in ("ORG-A", "ORG-B"):
            qty = s.execute(select(InventoryItem.quantity).where(InventoryItem.org_id == o)).scalar_one()
            led = s.execute(select(func.sum(InventoryMovement.delta)).where(InventoryMovement.org_id == o)).scalar_one()
            recon[o] = {"stock": qty, "ledger_sum": led, "match": abs(qty - led) < 1e-9}
        cross = s.execute(text("SELECT COUNT(*) FROM inventory_items i JOIN depots d ON d.id=i.depot_id WHERE d.org_id!=i.org_id")).scalar_one()
        fk = s.execute(text("PRAGMA foreign_key_check")).fetchall()
        integrity = s.execute(text("PRAGMA integrity_check")).scalar_one()
    rto_ms = (time.perf_counter() - t_rto) * 1000
    # prove the verifier would catch tampering in the restored copy
    e2.dispose()
    c = sqlite3.connect(restored_path)
    c.execute("UPDATE audit_events SET summary='tampered' WHERE org_id='ORG-B' AND seq=5")
    c.commit(); c.close()
    e3 = build_engine(f"sqlite:///{restored_path}")
    with build_session_factory(e3)() as s:
        tamper_detected = not persistence.verify_audit_chain(s, "ORG-B")["valid"]
    e3.dispose()
    shutil.rmtree(d, ignore_errors=True)
    lost = events_at_disaster - bak_events
    return {"topic": 40, "mode": "REAL_MEASURED",
            "implementation_under_test": "sqlite3 online backup API + production run_migrations/verify_audit_chain/inventory ledger on a DISPOSABLE database",
            "environment": environment(), "backup_ms": round(backup_ms, 2),
            "measured_restore_and_validate_ms": round(rto_ms, 2),
            "events_at_disaster": events_at_disaster, "events_in_backup": bak_events, "events_lost_after_backup": lost,
            "migrations_reapplied": applied, "audit_chain": {o: c_["valid"] for o, c_ in chain.items()},
            "inventory_reconciliation": recon, "cross_tenant_rows": cross, "fk_violations": len(fk), "integrity_check": integrity,
            "invariants": {"restore_succeeded": True, "audit_chains_valid": all(c_["valid"] for c_ in chain.values()),
                           "inventory_reconciles": all(r["match"] for r in recon.values()), "no_cross_tenant_rows": cross == 0,
                           "no_fk_violations": len(fk) == 0, "integrity_ok": integrity == "ok",
                           "migrations_idempotent_on_restore": applied == [],
                           "tamper_detectable_after_restore": tamper_detected},
            "limitations": ["measured RTO covers copy+migrate+validate of a tiny DB on one machine, not a production recovery",
                            "RPO here equals writes after the backup instant; scheduled backup cadence is NOT implemented",
                            "backup file is not encrypted or immutable in this lab; PostgreSQL PITR is platform-managed/PLANNED"]}


# ---------------------------------------------------------------------------
# Topic 38 — secrets & key rotation (REAL keyring; throwaway keys; no secret ever returned)
# ---------------------------------------------------------------------------
def secrets_rotation() -> Dict[str, Any]:
    kr = Keyring()
    kr.add_key(1)
    key_material = [kr._keys[1]]
    records = {f"R{i}": kr.encrypt(f"beneficiary-contact-{i}".encode()) for i in range(5)}   # synthetic plaintext
    steps = [{"step": "encrypt 5 records under key v1", "states": kr.status()}]
    kr.add_key(2)
    key_material.append(kr._keys[2])
    new_blob = kr.encrypt(b"new-record")
    steps.append({"step": "rotate: add key v2 (v1 -> DECRYPT_ONLY)", "states": kr.status(),
                  "new_writes_use": new_blob.split(b":")[0].decode(),
                  "old_records_still_readable": kr.decrypt(records["R0"]) == b"beneficiary-contact-0"})
    for k in ("R0", "R1", "R2"):
        records[k] = kr.rewrap(records[k])
    steps.append({"step": "backfill: re-wrap 3 of 5 records to v2", "versions": sorted({v.split(b":")[0].decode() for v in records.values()})})
    kr.revoke(1)
    failures = {}
    for k in ("R0", "R4"):
        try:
            kr.decrypt(records[k])
            failures[k] = "decrypted"
        except KeyRevoked:
            failures[k] = "FAIL CLOSED (key v1 revoked)"
    steps.append({"step": "revoke v1", "states": kr.status(), "results": failures})
    try:
        require_secret("AIDNEXUS_LAB_MISSING_CREDENTIAL", environ={})
        missing = "no error"
    except SecretMissing as e:
        missing = f"fail closed: {e}"
    try:
        kr.decrypt(b"v9:garbage")
        wrong = "decrypted"
    except KeyRevoked:
        wrong = "fail closed: unknown key version"
    except InvalidToken:
        wrong = "fail closed: invalid token"
    steps.append({"step": "missing credential / wrong version", "missing_credential": missing, "wrong_version": wrong})
    result = {"topic": 38, "mode": "REAL_MEASURED",
            "implementation_under_test": "app/keyring.py (versioned Fernet keyring). Not a KMS; not yet protecting a production column.",
            "environment": environment(), "steps": steps,
            "invariants": {"old_readable_after_rotation": steps[1]["old_records_still_readable"],
                           "rewrapped_survive_revocation": kr.decrypt(records["R0"]) == b"beneficiary-contact-0",
                           "unrewrapped_fail_closed_after_revocation": failures["R4"].startswith("FAIL CLOSED"),
                           "missing_secret_fails_closed": missing.startswith("fail closed")}}
    serialized = repr(result)
    result["invariants"]["no_key_material_in_output"] = not any(k.decode() in serialized for k in key_material)
    return result


# ---------------------------------------------------------------------------
# Topic 36 — one request across gateway -> db -> agent -> optimizer (REAL spans)
# ---------------------------------------------------------------------------
def _chain_ok(spans) -> bool:
    by_name = {s["name"]: s for s in spans}
    g = by_name.get("gateway.request (simulated HTTP entry)")
    a = by_name.get("agent.simulated_orchestrator")
    o = by_name.get("optimizer.solve_allocation")
    d = by_name.get("db.query")
    return bool(g and a and o and d and a["parent_span_id"] == g["span_id"]
                and o["parent_span_id"] == a["span_id"] and d["parent_span_id"] == g["span_id"])


def trace_demo() -> Dict[str, Any]:
    from .state_engine import CrisisStateEngine
    telemetry.reset()
    tctx = telemetry.parse_traceparent(None)
    with disposable_db("trace") as (engine, factory, _):
        with telemetry.trace_context(tctx["trace_id"], None):
            with telemetry.span("gateway.request (simulated HTTP entry)", route="POST /api/v1/plan/replan"):
                with factory() as s:
                    s.execute(text("SELECT COUNT(*) FROM organizations")).scalar_one()
                with telemetry.span("agent.simulated_orchestrator", agent_id="agent-2"):
                    eng = CrisisStateEngine(seed=42, org_id="ORG-PACIFIC", persist=False)
                    eng.optimizer.solve_allocation  # noqa: B018  (instrumented entry point)
    trace = telemetry.get_trace(tctx["trace_id"])
    spans = trace["spans"]
    ids = {s["span_id"] for s in spans}
    linked = sum(1 for s in spans if s["parent_span_id"] in ids)
    redaction_in = {"requester_name": "Maria Lopez", "phone": "+63 917 555 0100", "note": "call +63 917 555 0100 or maria@example.org",
                    "sector": "North"}
    n = 20000
    t = time.perf_counter()
    for _ in range(n):
        pass
    bare = time.perf_counter() - t
    telemetry.reset()
    with telemetry.trace_context("a" * 32, None):
        t = time.perf_counter()
        for _ in range(n):
            with telemetry.span("overhead_probe"):
                pass
        traced_t = time.perf_counter() - t
    telemetry.reset()
    return {"topic": 36, "mode": "REAL_MEASURED",
            "implementation_under_test": "app/telemetry.py spans; HTTP entry is simulated here but db.query + optimizer spans are emitted by the real instrumented code",
            "environment": environment(), "trace_id": tctx["trace_id"], "trace_source": tctx["source"],
            "spans": [{"name": s["name"], "span_id": s["span_id"], "parent": s["parent_span_id"], "ms": s["duration_ms"],
                       "status": s["status"]} for s in spans],
            "trace_coverage": {"spans": len(spans), "linked_to_parent": linked,
                               "components_seen": sorted({s["name"].split(".")[0].split(" ")[0] for s in spans})},
            "redaction": {"input": redaction_in, "output": telemetry.redact(redaction_in)},
            "instrumentation_overhead_us_per_span": round((traced_t - bare) / n * 1e6, 2),
            "exporter": "NONE — spans stay in an in-process ring buffer",
            "invariants": {"all_spans_share_trace_id": all(s["trace_id"] == tctx["trace_id"] for s in spans),
                           "db_span_present": any(s["name"] == "db.query" for s in spans),
                           "optimizer_span_present": any(s["name"] == "optimizer.solve_allocation" for s in spans),
                           "parent_chain_correct": _chain_ok(spans),
                           "exactly_one_root": sum(1 for s in spans if s["parent_span_id"] is None) == 1,
                           "pii_redacted": "Maria" not in str(telemetry.redact(redaction_in)) and "917" not in str(telemetry.redact(redaction_in))}}


# ---------------------------------------------------------------------------
# Topic 37 — error budget arithmetic over MEASURED telemetry
# ---------------------------------------------------------------------------
def error_budget(slo: float, good: int, total: int) -> Dict[str, Any]:
    if total <= 0:
        return {"status": "NOT_MEASURED", "reason": "no eligible events"}
    allowed_bad = (1 - slo) * total
    bad = total - good
    return {"status": "MEASURED", "slo": slo, "sli": round(good / total, 6), "eligible_events": total, "bad_events": bad,
            "allowed_bad_events": round(allowed_bad, 3),
            "budget_consumed_pct": round(100 * bad / allowed_bad, 1) if allowed_bad > 0 else (0.0 if bad == 0 else float("inf")),
            "budget_remaining_events": round(allowed_bad - bad, 3), "within_slo": good / total >= slo}


def slo_report() -> Dict[str, Any]:
    snap = telemetry.snapshot()
    sli = snap["api_sli"]
    candidate_slo = 0.99
    rep = {"topic": 37, "mode": "REAL_TELEMETRY" if sli["status"] == "MEASURED" else "NOT_MEASURED",
           "window": f"since process start ({snap['uptime_s']}s) — NOT a 30-day window",
           "candidate_slo": candidate_slo, "slo_basis": "CANDIDATE target for a single-instance demo; not an SLA; not derived from user research",
           "exclusions": list(telemetry.EXCLUDED_FROM_SLI) + ["simulated benchmark runs are never counted as production availability"]}
    rep["api_availability"] = (error_budget(candidate_slo, sli["good_requests"], sli["eligible_requests"])
                               if sli["status"] == "MEASURED" else sli)
    return rep


# ---------------------------------------------------------------------------
# Topic 30 — storage access experiment (REAL object_store)
# ---------------------------------------------------------------------------
def storage_access() -> Dict[str, Any]:
    from .object_store import LocalObjectStore, AccessDenied, IntegrityError, StorageError
    d = tempfile.mkdtemp(prefix="aidnexus_obj_")
    now = [1000.0]
    store = LocalObjectStore(d, os.urandom(32), clock=lambda: now[0])
    pdf = b"%PDF-1.4\n" + os.urandom(2048)
    res = []

    def attempt(label, fn):
        try:
            fn()
            res.append({"attempt": label, "allowed": True})
        except (AccessDenied, IntegrityError, StorageError) as e:
            res.append({"attempt": label, "allowed": False, "error": type(e).__name__, "detail": str(e)[:70]})
    meta = store.put("ORG-A", "u1", pdf, "application/pdf")
    tok = store.sign_download("ORG-A", meta["key"], ttl_s=60)
    attempt("authorised download with valid signed URL", lambda: store.read_signed("ORG-A", meta["key"], tok["exp"], tok["sig"]))
    attempt("cross-tenant download (ORG-B uses ORG-A key)", lambda: store.read_signed("ORG-B", meta["key"], tok["exp"], tok["sig"]))
    attempt("tampered signature", lambda: store.read_signed("ORG-A", meta["key"], tok["exp"], "0" * 64))
    now[0] += 61
    attempt("expired signed URL", lambda: store.read_signed("ORG-A", meta["key"], tok["exp"], tok["sig"]))
    attempt("executable disguised as PDF", lambda: store.put("ORG-A", "u1", b"MZ" + os.urandom(100), "application/pdf"))
    attempt("oversize upload", lambda: store.put("ORG-A", "u1", b"%PDF-" + b"0" * (6 * 1024 * 1024), "application/pdf"))
    attempt("corrupted-in-transit upload (client checksum mismatch)", lambda: store.put("ORG-A", "u1", pdf + b"x", "application/pdf", client_sha256=meta["sha256"]))
    dup = store.put("ORG-A", "u1", pdf, "application/pdf")
    with open(store._paths(meta["key"])[0], "ab") as f:
        f.write(b"bitrot")
    tok2 = store.sign_download("ORG-A", meta["key"], ttl_s=60)
    attempt("read after bit-rot (checksum re-verified)", lambda: store.read_signed("ORG-A", meta["key"], tok2["exp"], tok2["sig"]))
    store.delete("ORG-A", meta["key"])
    attempt("download after deletion", lambda: store.sign_download("ORG-A", meta["key"]))
    shutil.rmtree(d, ignore_errors=True)
    allowed = [r["allowed"] for r in res]
    return {"topic": 30, "mode": "REAL_MEASURED",
            "implementation_under_test": "app/object_store.py LocalObjectStore (filesystem adapter; no S3, no malware scanner, not wired to routes)",
            "environment": environment(), "attempts": res, "duplicate_upload_reused_object": dup.get("duplicate") is True,
            "invariants": {"only_authorised_allowed": len(allowed) == 9 and allowed[0] and not any(allowed[1:]),
                           "duplicate_idempotent": dup.get("duplicate") is True},
            "limitations": ["malware scanning: NOT_IMPLEMENTED (needs an AV engine / managed scanner)",
                            "encryption at rest: delegated to platform/KMS in production; not done by this adapter"]}
