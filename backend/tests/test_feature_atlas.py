"""Feature catalog validation gate (Phase III).

The atlas is a capability PORTFOLIO, not an implementation counter: statuses
are evidence-backed and enforced by scripts/validate_feature_atlas.py, which
this test executes as a gate.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_feature_atlas_valid():
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "validate_feature_atlas.py")],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, f"atlas invalid:\n{result.stdout}\n{result.stderr}"
    assert "ATLAS VALID" in result.stdout


def test_atlas_portfolio_size_and_domains():
    path = os.path.join(ROOT, "docs", "product", "feature-atlas.jsonl")
    import json
    from collections import Counter
    records = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    portfolio = [r for r in records if r["current_status"] != "REJECTED"]
    assert len(portfolio) >= 1080
    domains = Counter(r["domain_id"] for r in portfolio)
    assert len(domains) == 36
    assert all(c >= 30 for c in domains.values())
    # verified claims carry real test references
    for r in portfolio:
        if r["current_status"] == "EXISTING_VERIFIED":
            assert r["test_references"]
            assert not all(t.startswith("tests/planned/") for t in r["test_references"])
