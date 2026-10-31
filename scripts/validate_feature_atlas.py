#!/usr/bin/env python3
"""Validates the AIDNEXUS ONE feature atlas.

Checks: record count, unique ids, unique semantic descriptions, exactly 36
domains, >=30 features per domain, required fields, valid priority and status
values, test-reference presence for verified statuses, dependency references,
and duplicate-similarity warnings.
Exit code 1 on any hard failure.
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSONL = os.path.join(ROOT, "docs", "product", "feature-atlas.jsonl")

REQUIRED = ["feature_id", "domain_id", "name", "description", "problem",
            "primary_actor", "user_outcome", "trigger", "inputs", "outputs",
            "workflow", "data_entities", "api_or_actions", "authorization",
            "business_invariants", "safety_requirements", "success_metrics",
            "acceptance_criteria", "test_references", "dependencies",
            "failure_modes", "fallback_behavior", "evidence", "evidence_confidence",
            "current_status", "priority", "impact_score", "risk_score",
            "implementation_effort", "taste_requirements", "cloud_requirements",
            "outsystems_mapping", "implementation_notes"]

VALID_STATUS = {"EXISTING_VERIFIED", "EXISTING_UNVERIFIED", "PARTIALLY_IMPLEMENTED",
                "PROPOSED", "IN_DEVELOPMENT", "IMPLEMENTED_UNVERIFIED",
                "IMPLEMENTED_TESTED", "BLOCKED_EXTERNAL_DEPENDENCY", "DEPRECATED", "REJECTED"}
VALID_PRIORITY = {"P0", "P1", "P2", "P3", "P4"}
VALID_EFFORT = {"S", "M", "L"}


def main():
    records = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    errors, warnings = [], []
    portfolio = [r for r in records if r["current_status"] != "REJECTED"]

    # 1. totals
    if len(records) < 1080 + len([r for r in records if r["current_status"] == "REJECTED"]) * 0:
        pass  # explicit checks below
    if len(portfolio) < 1080:
        errors.append(f"portfolio count {len(portfolio)} < 1080")
    if len(records) < 1080:
        errors.append(f"total records {len(records)} < 1080")

    # 2. unique ids
    ids = Counter(r["feature_id"] for r in records)
    dupes = [i for i, n in ids.items() if n > 1]
    if dupes:
        errors.append(f"duplicate feature ids: {dupes[:5]}")

    # 3. unique names + descriptions
    names = Counter(r["name"].strip().lower() for r in records)
    dup_names = [n for n, c in names.items() if c > 1]
    if dup_names:
        errors.append(f"duplicate feature names: {dup_names[:5]}")
    descs = Counter(r["description"].strip() for r in records)
    dup_desc = [d[:60] for d, c in descs.items() if c > 1]
    if dup_desc:
        errors.append(f"duplicate descriptions: {dup_desc[:3]}")

    # 4. exactly 36 domain groups (portfolio), >=30 each
    domain_counts = Counter(r["domain_id"] for r in portfolio)
    if len(domain_counts) != 36:
        errors.append(f"domain count {len(domain_counts)} != 36")
    under = {d: c for d, c in domain_counts.items() if c < 30}
    if under:
        errors.append(f"domains under 30 features: {under}")

    # 5. required fields
    for r in records:
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            errors.append(f"{r.get('feature_id')}: missing fields {missing}")
            continue
        for field in ("inputs", "outputs", "workflow", "data_entities",
                      "authorization", "business_invariants", "safety_requirements",
                      "success_metrics", "acceptance_criteria", "test_references",
                      "dependencies", "failure_modes", "evidence",
                      "taste_requirements", "cloud_requirements", "outsystems_mapping"):
            if not isinstance(r[field], list) or len(r[field]) == 0:
                errors.append(f"{r['feature_id']}: empty list field {field}")

    # 6. enum validity
    for r in records:
        if r["current_status"] not in VALID_STATUS:
            errors.append(f"{r['feature_id']}: invalid status {r['current_status']}")
        if r["priority"] not in VALID_PRIORITY:
            errors.append(f"{r['feature_id']}: invalid priority {r['priority']}")
        if r["implementation_effort"] not in VALID_EFFORT:
            errors.append(f"{r['feature_id']}: invalid effort {r['implementation_effort']}")
        if r["evidence_confidence"] not in ("high", "medium", "low"):
            errors.append(f"{r['feature_id']}: invalid confidence")
        if not (1 <= r["impact_score"] <= 5 and 1 <= r["risk_score"] <= 5):
            errors.append(f"{r['feature_id']}: scores out of range")
        if not (0 <= r.get("priority_score", 0) <= 100):
            errors.append(f"{r['feature_id']}: priority score out of range")

    # 7. verified statuses need real test refs (not planned/) and evidence
    for r in records:
        if r["current_status"] == "EXISTING_VERIFIED":
            if not r["test_references"] or all(t.startswith("tests/planned/") for t in r["test_references"]):
                errors.append(f"{r['feature_id']}: EXISTING_VERIFIED without real test reference")
            if any("no runtime evidence" in e for e in r["evidence"]):
                errors.append(f"{r['feature_id']}: EXISTING_VERIFIED without runtime evidence")

    # 8. dependency references: must be feature ids, wave foundations, or empty
    all_ids = set(ids)
    for r in records:
        for dep in r["dependencies"]:
            if dep.startswith(("platform ", "Wave ")):
                continue
            base = dep.split()[0]
            if base not in all_ids:
                warnings.append(f"{r['feature_id']}: dependency not a feature id: {dep[:60]}")

    # 9. similarity warnings (token overlap heuristic)
    def tokens(name):
        return set(name.lower().split())
    by_domain = {}
    for r in portfolio:
        by_domain.setdefault(r["domain_id"], []).append(r)
    for dom, feats in by_domain.items():
        for i in range(len(feats)):
            for j in range(i + 1, len(feats)):
                a, b = tokens(feats[i]["name"]), tokens(feats[j]["name"])
                if not a or not b:
                    continue
                overlap = len(a & b) / min(len(a), len(b))
                if overlap >= 0.8:
                    warnings.append(f"similar names in {dom}: '{feats[i]['name']}' vs '{feats[j]['name']}'")

    print(f"records={len(records)} portfolio={len(portfolio)} domains={len(domain_counts)}")
    status_counts = Counter(r["current_status"] for r in records)
    print("by status:", dict(status_counts))
    print(f"errors={len(errors)} warnings={len(warnings)}")
    for e in errors[:10]:
        print("ERROR:", e)
    for w in warnings[:10]:
        print("WARN:", w)
    if errors:
        sys.exit(1)
    print("ATLAS VALID")


if __name__ == "__main__":
    main()
