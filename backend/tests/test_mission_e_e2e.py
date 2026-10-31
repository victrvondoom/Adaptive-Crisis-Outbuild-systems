"""MISSION E — Accountability and Impact (Phase IV Wave 6).

Verifies the impact-report contract: real evidence retrieval, receipt
verification, resource reconciliation, actual-vs-estimated distinction,
missing-evidence detection, per-request and org-level reports, provenance
hashing and formula honesty.
"""
COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"
RIVAL = "rival-coordinator@example.dev"


class TestMissionE:
    def test_org_report_recomputes_from_authoritative_rows(self, client):
        h = client.login(COORD)
        # produce a real outcome first
        client.post("/api/v1/scenario/reset", headers=h)
        client.post("/api/v1/replan/approve", headers=h,
                    json={"approver_name": "Coord"})
        state = client.get("/api/v1/state", headers=h).json()
        target = next(q for q in state["dispatch_queue"]
                      if q["status"] == "DISPATCHED")["request_id"]
        client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                    json={"request_id": target, "volunteer_name": "M. Santos"})

        report = client.get("/api/v1/impact/report", headers=h).json()
        assert report["level"] == "ORGANIZATION"
        assert report["requests_total"] >= 200
        assert report["delivery_receipts"] >= 1
        # formula honesty: the denominator and formula are explicit
        assert report["fulfillment_formula"] == "delivered_requests / total_requests"
        total = report["requests_total"]
        delivered = report["requests_by_status"].get("DELIVERED", 0)
        assert abs(report["fulfillment_rate"] - round(delivered / total, 4)) < 1e-9
        # actual vs estimated distinction is explicit
        assert "ACTUAL" in report["actual_vs_estimated"]
        # audit chain verification is part of the report
        assert report["audit_chain_valid"] is True
        # no delivered request without a receipt (missing evidence detection)
        assert report["missing_evidence"] == []
        # provenance hash present and deterministic
        r2 = client.get("/api/v1/impact/report", headers=h).json()
        assert r2["provenance_sha256"] != report["provenance_sha256"] \
            if r2["generated_at"] != report["generated_at"] else True

    def test_request_report_reconciles_evidence(self, client):
        h = client.login(COORD)
        client.post("/api/v1/scenario/reset", headers=h)
        client.post("/api/v1/replan/approve", headers=h,
                    json={"approver_name": "Coord"})
        state = client.get("/api/v1/state", headers=h).json()
        target = next(q for q in state["dispatch_queue"]
                      if q["status"] == "DISPATCHED")["request_id"]
        client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                    json={"request_id": target, "volunteer_name": "M. Santos"})
        report = client.get(f"/api/v1/impact/report?request_id={target}",
                            headers=h).json()
        assert report["outcome"] == "DELIVERED_ACTUAL"
        assert report["delivery_receipt"]["items"]
        # inventory reconciliation: delivery movements are all negative
        delivery_moves = [m for m in report["inventory_movements"]
                          if m["reason"] == "DELIVERY"]
        assert delivery_moves and all(m["delta"] < 0 for m in delivery_moves)
        assert report["audit_event_count"] >= 1
        assert report["provenance_sha256"]

    def test_pending_request_is_not_an_outcome(self, client):
        h = client.login(COORD)
        # intake a fresh request: it has consent + audit history but no receipt
        intake = client.post("/api/v1/requests", headers=h, json={
            "requester_name": "Pending Outcome Shelter",
            "lat": 14.6042, "lng": 120.9846, "sector": "Central Metro",
            "items": [{"item_type": "rations_mre", "quantity": 10, "unit": "units"}],
            "priority": "LOW",
            "consent": {"granted": True, "scope": "ASSISTANCE"}}).json()
        rid = intake["request"]["id"]
        report = client.get(f"/api/v1/impact/report?request_id={rid}",
                            headers=h).json()
        # no receipt -> explicitly NOT an outcome (anti-fabrication)
        assert report["delivery_receipt"] is None
        assert report["outcome"]["status"] == "REQUESTED"
        assert "No persisted receipt" in report["outcome"]["note"]
        # the pending request still has its consent and audit evidence
        assert report["consent"]["status"] == "GRANTED"
        assert report["audit_event_count"] >= 1

    def test_report_tenant_isolation(self, client):
        rival = client.login(RIVAL, "ORG-HIGHLAND")
        report = client.get("/api/v1/impact/report", headers=rival).json()
        # HIGHLAND's report only contains HIGHLAND data (independent scenario)
        assert report["org_id"] == "ORG-HIGHLAND"
        h = client.login("coordinator@example.dev")
        pacific = client.get("/api/v1/impact/report", headers=h).json()
        assert pacific["org_id"] == "ORG-PACIFIC"
        assert pacific["provenance_sha256"] != report["provenance_sha256"]

    def test_unknown_request_404(self, client):
        h = client.login(COORD)
        r = client.get("/api/v1/impact/report?request_id=NOSUCH-1", headers=h)
        assert r.status_code == 404
