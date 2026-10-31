"""Dynamic Feature Atlas service: serves the 1,080-feature portfolio at
runtime with live filtering, pagination, summary statistics and integrity
validation. The JSONL registry is the source of truth; the cache reloads
whenever the file changes (mtime-checked), so regenerated atlases are picked
up without a restart."""
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
JSONL = os.path.join(ROOT, "docs", "product", "feature-atlas.jsonl")
VALIDATOR = os.path.join(ROOT, "scripts", "validate_feature_atlas.py")

_cache: Dict[str, Any] = {"mtime": None, "records": [], "loaded": 0.0}


def _load() -> List[Dict[str, Any]]:
    try:
        mtime = os.path.getmtime(JSONL)
    except OSError:
        return []
    if _cache["mtime"] != mtime:
        records = []
        with open(JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        _cache["mtime"] = mtime
        _cache["records"] = records
        _cache["loaded"] = time.time()
    return _cache["records"]


def portfolio():
    return [r for r in _load() if r.get("current_status") != "REJECTED"]


def query_features(domain: Optional[str] = None, status: Optional[str] = None,
                   priority: Optional[str] = None, search: Optional[str] = None,
                   limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Filter + paginate the portfolio. Search matches id, name, description."""
    rows = portfolio()
    if domain:
        rows = [r for r in rows if r["domain_id"] == domain.upper()]
    if status:
        rows = [r for r in rows if r["current_status"] == status]
    if priority:
        rows = [r for r in rows if r["priority"] == priority]
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in r["feature_id"].lower()
                or needle in r["name"].lower()
                or needle in r["description"].lower()]
    total = len(rows)
    rows = rows[offset:offset + limit]
    return {"total": total, "limit": limit, "offset": offset,
            "returned": len(rows), "features": rows}


def get_feature(feature_id: str) -> Optional[Dict[str, Any]]:
    for r in _load():
        if r["feature_id"] == feature_id:
            return r
    return None


def summary() -> Dict[str, Any]:
    from collections import Counter
    records = _load()
    port = [r for r in records if r.get("current_status") != "REJECTED"]
    status_counts = Counter(r["current_status"] for r in records)
    domain_counts = Counter(r["domain_id"] for r in port)
    priority_counts = Counter(r["priority"] for r in port)
    return {
        "total_records": len(records),
        "portfolio": len(port),
        "domains": len(domain_counts),
        "min_per_domain": min(domain_counts.values()) if domain_counts else 0,
        "max_per_domain": max(domain_counts.values()) if domain_counts else 0,
        "by_status": dict(status_counts),
        "by_priority": dict(priority_counts),
        "by_domain": dict(sorted(domain_counts.items())),
        "registry_mtime": _cache["mtime"],
        "loaded_at": _cache["loaded"],
    }


def domain_catalog() -> List[Dict[str, Any]]:
    """Domain rollup with live counts and status breakdowns."""
    port = portfolio()
    domains: Dict[str, Dict[str, Any]] = {}
    for r in port:
        d = domains.setdefault(r["domain_id"], {
            "domain_id": r["domain_id"], "features": 0,
            "verified": 0, "implemented_tested": 0, "partially_implemented": 0,
            "blocked": 0, "proposed": 0, "avg_priority_score": 0.0})
        d["features"] += 1
        s = r["current_status"]
        if s == "EXISTING_VERIFIED":
            d["verified"] += 1
        elif s == "IMPLEMENTED_TESTED":
            d["implemented_tested"] += 1
        elif s == "PARTIALLY_IMPLEMENTED":
            d["partially_implemented"] += 1
        elif s == "BLOCKED_EXTERNAL_DEPENDENCY":
            d["blocked"] += 1
        elif s == "PROPOSED":
            d["proposed"] += 1
        d["avg_priority_score"] += r.get("priority_score", 0)
    for d in domains.values():
        d["avg_priority_score"] = round(d["avg_priority_score"] / d["features"], 1)
    return sorted(domains.values(), key=lambda x: x["domain_id"])


def validate() -> Dict[str, Any]:
    """Runs the atlas validator; returns structured results (admin endpoint)."""
    try:
        result = subprocess.run([sys.executable, VALIDATOR],
                                capture_output=True, text=True, cwd=ROOT, timeout=60)
        return {"valid": result.returncode == 0,
                "exit_code": result.returncode,
                "output": result.stdout[-4000:]}
    except Exception as e:
        return {"valid": False, "exit_code": -1, "output": f"validator failed: {e}"}
