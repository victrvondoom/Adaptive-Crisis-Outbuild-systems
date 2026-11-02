"""Registry + CLI for the Phase VI laboratory. `python -m app.advanced_runner` writes reproducible
benchmark artifacts to benchmarks/phase6/ (raw runs, median/p95 across runs, commit, environment)."""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
from typing import Any, Callable, Dict

from . import advanced_lab as L
from . import advanced_lab_ext as E

REGISTRY: Dict[str, tuple] = {
    "integrity": (21, L.integrity_probe), "index": (22, L.index_experiment),
    "contention": (23, L.inventory_contention), "pool": (24, L.pool_saturation),
    "replica": (25, E.replica_routing), "sharding": (26, E.shard_routing), "cap": (27, E.cap_partition),
    "lease": (28, E.lease_fencing), "storage": (30, E.storage_access), "cdn": (31, None),
    "search": (32, E.search_index), "realtime": (33, E.realtime_reconnect), "backpressure": (34, E.backpressure),
    "schema": (35, E.schema_evolution), "trace": (36, E.trace_demo), "slo": (37, E.slo_report),
    "secrets": (38, E.secrets_rotation), "region": (39, E.multi_region), "backup": (40, E.backup_restore),
}


def capture_cdn() -> Dict[str, Any]:
    """Real response headers from this application, fed to the edge model."""
    from fastapi.testclient import TestClient
    from .main import app
    c = TestClient(app)
    headers = {}
    for path in ("/js/app.js", "/css/style.css", "/api/v1/me"):
        r = c.get(path)
        headers[path] = {k.lower(): v for k, v in r.headers.items() if k.lower() in ("cache-control", "etag", "last-modified")}
    return E.cdn_edge(headers)


def run(name: str) -> Dict[str, Any]:
    if name not in REGISTRY:
        raise KeyError(name)
    topic, fn = REGISTRY[name]
    t = time.perf_counter()
    out = capture_cdn() if name == "cdn" else fn()
    out["lab_name"] = name
    out["wall_ms"] = round((time.perf_counter() - t) * 1000, 1)
    out["run_label"] = ("SIMULATED — modelled infrastructure, not live" if out.get("mode") == "SIMULATED"
                        else "REAL_MEASURED — executed now on a disposable database/process")
    return out


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(__file__),
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(repeats: int = 5) -> str:
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "benchmarks", "phase6"))
    os.makedirs(out_dir, exist_ok=True)
    art: Dict[str, Any] = {"commit": _commit(), "seed": L.LAB_SEED, "environment": L.environment(),
                           "repeats": repeats, "generated_unix": int(time.time()), "experiments": {}}
    for name in ("index", "contention", "pool", "lease", "backpressure", "search", "schema", "backup", "trace", "storage", "secrets"):
        runs = []
        for _ in range(repeats if name in ("contention", "pool", "lease", "backpressure", "backup", "search", "trace") else max(1, repeats // 2)):
            runs.append(run(name))
        wall = [r["wall_ms"] for r in runs]
        invariants_ok = all(all(r["invariants"].values()) for r in runs if "invariants" in r)
        art["experiments"][name] = {"topic": REGISTRY[name][0], "runs": len(runs), "all_invariants_held_every_run": invariants_ok,
                                    "wall_ms": {"median": round(statistics.median(wall), 1), "max": max(wall), "min": min(wall)},
                                    "raw_last_run": runs[-1], "limitations": runs[-1].get("limitations", [])}
    for name in ("integrity", "replica", "sharding", "cap", "region", "realtime"):
        art["experiments"][name] = {"topic": REGISTRY[name][0], "runs": 1, "raw_last_run": run(name)}
    path = os.path.join(out_dir, f"phase6_lab_{art['commit']}.json")
    with open(path, "w") as f:
        json.dump(art, f, indent=2, default=str)
    return path


if __name__ == "__main__":
    print(main())
