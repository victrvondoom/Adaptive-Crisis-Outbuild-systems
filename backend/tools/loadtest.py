"""AIDNEXUS ONE load test — measures real latency/RPS against a live server.

Usage:  python tools/loadtest.py [port]
Writes: docs/phase-2/benchmarks/loadtest_results.json

Honest methodology: fixed request mix (state read + dispatch-queue read +
health), N virtual users issuing sequential requests per user, measured with
httpx. This is a single-process smoke load test, NOT a production-scale
benchmark — see report for limitations.
"""
import json
import os
import statistics
import subprocess
import sys
import threading
import time
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import httpx

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.abspath(os.path.join(BACKEND, "..", "docs", "phase-2", "benchmarks",
                                   "loadtest_results.json"))


def wait_ready(base):
    for _ in range(60):
        try:
            if httpx.get(f"{base}/readyz", timeout=2).status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def run_users(base, token, org, n_users, requests_per_user):
    latencies = []
    errors = []
    lock = threading.Lock()
    barrier = threading.Barrier(n_users)

    def worker():
        barrier.wait()
        h = {"Authorization": f"Bearer {token}", "X-Org-Id": org}
        for i in range(requests_per_user):
            path = ["/api/v1/state", "/api/v1/dispatch-queue", "/healthz"][i % 3]
            t0 = time.perf_counter()
            try:
                r = httpx.get(base + path, headers=h, timeout=15)
                dt = (time.perf_counter() - t0) * 1000
                with lock:
                    latencies.append(dt)
                    if r.status_code != 200:
                        errors.append(r.status_code)
            except Exception as e:
                with lock:
                    errors.append(type(e).__name__)

    threads = [threading.Thread(target=worker) for _ in range(n_users)]
    start = time.perf_counter()
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.perf_counter() - start
    lat = sorted(latencies)
    def pct(p):
        return round(lat[min(int(len(lat) * p), len(lat) - 1)], 1) if lat else None
    return {
        "users": n_users,
        "requests": len(lat) + len(errors),
        "rps": round(len(lat) / wall, 1),
        "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
        "max_ms": round(lat[-1], 1) if lat else None,
        "errors": len(errors), "error_types": sorted(set(map(str, errors))),
        "wall_seconds": round(wall, 1),
    }


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    db = f"sqlite:///{BACKEND}/data/loadtest_{uuid.uuid4().hex[:6]}.db"
    env = dict(os.environ)
    env.update({"DATABASE_URL": db, "APP_ENV": "development",
                "DEV_AUTH_ENABLED": "1"})
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        if not wait_ready(base):
            print("server failed to become ready")
            sys.exit(1)
        tok = httpx.post(f"{base}/api/v1/auth/dev/token",
                         json={"email": "coordinator@example.dev"}).json()
        results = {"environment": "local uvicorn + SQLite WAL, single process",
                   "timestamp": time.time(), "runs": []}
        for users in (10, 25, 50):
            r = run_users(base, tok["access_token"], "ORG-PACIFIC", users, 15)
            results["runs"].append(r)
            print(f"{users:3d} users: {r['rps']} req/s | p50 {r['p50_ms']}ms | "
                  f"p95 {r['p95_ms']}ms | p99 {r['p99_ms']}ms | errors {r['errors']}")
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(results, f, indent=2)
        print("wrote", OUT)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
