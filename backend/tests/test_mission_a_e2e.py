"""MISSION A — Request to Verified Assistance (Phase IV Wave 3).

End-to-end chain: intake (schema + consent + dedup) -> canonical priority ->
plan -> human approval -> dispatch -> delivery confirmation -> inventory
deducted exactly once -> evidence-linked mission receipt (trace + impact).
Every step goes through the real API against a real database.
"""
COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"
ADMIN = "ngo-admin@example.dev"

INTAKE = {
    "requester_name": "Barangay San Rafael Shelter",
    "lat": 14.6042, "lng": 120.9846, "sector": "Central Metro",
    "items": [{"item_type": "rations_mre", "quantity": 40, "unit": "units"},
              {"item_type": "potable_water_liters", "quantity": 120, "unit": "liters"}],
    "priority": "HIGH",
    "deadline_hours": 48.0, "affected_people": 55,
    "consent": {"granted": True, "scope": "ASSISTANCE",
                "evidence": "verbal consent recorded by field officer"},
}


class TestMissionA:
    def test_01_intake_creates_traceable_work_order(self, client):
        h = client.login(COORD)
        r = client.post("/api/v1/requests", headers=h, json=INTAKE)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["request"]["status"] == "REQUESTED"
        assert body["request"]["intake_channel"] == "API_INTAKE"
        assert body["consent"]["consent_id"].startswith("CON-")
        assert body["duplicate_of_id"] is None
        assert body["evidence"]["priority_reason"]
        # single source of truth: engine state sees the new request
        state = client.get("/api/v1/state", headers=h).json()
        assert any(r["id"] == body["request"]["id"] for r in state["requests"])
        assert state["stats"]["total_requests"] == 201

    def test_02_intake_rejects_unknown_item_type(self, client):
        h = client.login(COORD)
        bad = dict(INTAKE)
        bad["items"] = [{"item_type": "luxury_yachts", "quantity": 1, "unit": "x"}]
        r = client.post("/api/v1/requests", headers=h, json=bad)
        assert r.status_code == 422
        assert "Unknown item_type" in r.json()["detail"]

    def test_03_intake_requires_consent(self, client):
        h = client.login(COORD)
        bad = dict(INTAKE)
        bad["consent"] = {"granted": False}
        r = client.post("/api/v1/requests", headers=h, json=bad)
        assert r.status_code == 400
        assert "consent" in r.json()["detail"]

    def test_04_duplicate_intake_detected_never_denied(self, client):
        h = client.login(COORD)
        r1 = client.post("/api/v1/requests", headers=h, json=INTAKE)
        # second intake: same requester, same items, same place, same window
        r2 = client.post("/api/v1/requests", headers=h, json=INTAKE)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["duplicate_of_id"] == r1.json()["request"]["id"]
        # duplicate is routed to HUMAN review, never auto-denied
        assert body2["request"]["status"] == "UNDER_REVIEW"

    def test_05_full_chain_to_verified_assistance(self, client):
        """The complete chain: plan -> approve -> deliver -> receipt -> impact."""
        h = client.login(COORD)
        # baseline: reset (the initial plan is auto-activated by bootstrap)
        client.post("/api/v1/scenario/reset", headers=h)

        # intake a fresh request
        intake = client.post("/api/v1/requests", headers=h, json=INTAKE).json()
        rid = intake["request"]["id"]

        # re-plan through a disruption-free recovery: inject a minor disruption
        # to force replanning (the only sanctioned plan-mutation path)
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "WEATHER_HAZARD", "title": "Replan trigger",
            "description": "Minor weather advisory forces replan",
            "lat": 14.40, "lng": 120.90, "hazard_radius_km": 0.5})
        assert r.status_code == 200
        approve = client.post("/api/v1/replan/approve", headers=h,
                              json={"approver_name": "Coord"})
        assert approve.status_code == 200

        # the request must now be either scheduled (queue) or blocked WITH reason
        state = client.get("/api/v1/state", headers=h).json()
        queue_ids = {q["request_id"] for q in state["dispatch_queue"]}
        blocked = {b["request_id"]: b for b in state["blocked_requests"]}
        assert rid in queue_ids or rid in blocked
        if rid in blocked:
            assert blocked[rid].get("reason") or blocked[rid].get("feasibility")

        # deliver a dispatched request from the approved plan
        dispatched = next(q for q in state["dispatch_queue"]
                          if q["status"] == "DISPATCHED")
        target = dispatched["request_id"]
        r1 = client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                         json={"request_id": target, "volunteer_name": "M. Santos"})
        assert r1.status_code == 200, r1.text
        # idempotent: second confirmation is a duplicate, no second deduction
        r2 = client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                         json={"request_id": target, "volunteer_name": "M. Santos"})
        assert r2.json()["duplicate"] is True

        # evidence-linked mission receipt: trace shows receipt + movements + consent
        trace = client.get(f"/api/v1/requests/{target}", headers=h).json()
        assert trace["outcome"] == "DELIVERED_ACTUAL"
        assert trace["delivery_receipt"]["signature_hash"]
        assert trace["inventory_movements"]
        assert all(m["delta"] < 0 for m in trace["inventory_movements"]
                   if m["reason"] == "DELIVERY")

        # impact report for the delivered request
        impact = client.get(f"/api/v1/impact/report?request_id={target}",
                            headers=h).json()
        assert impact["level"] == "REQUEST"
        assert impact["delivery_receipt"] is not None
        assert impact["provenance_sha256"]

        # audit chain still verifies after all these mutations
        audit = client.get("/api/v1/audit?contains=intake", headers=h).json()
        assert audit["chain_valid"] is True

    def test_06_consent_revocation_blocks_delivery(self, client):
        h = client.login(COORD)
        intake = client.post("/api/v1/requests", headers=h, json=INTAKE).json()
        rid = intake["request"]["id"]
        # revoke consent
        r = client.post(f"/api/v1/requests/{rid}/consent/revoke", headers=h)
        assert r.status_code == 200
        # delivery confirmation is blocked (409) until human resolution
        r = client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                        json={"request_id": rid, "volunteer_name": "V"})
        assert r.status_code == 409
        assert "revoked" in r.json()["detail"].lower()
        # trace shows the revoked consent
        trace = client.get(f"/api/v1/requests/{rid}", headers=h).json()
        assert trace["consent"]["status"] == "REVOKED"

    def test_07_tenant_isolation_of_traces(self, client):
        h = client.login(COORD)
        intake = client.post("/api/v1/requests", headers=h, json=INTAKE).json()
        rid = intake["request"]["id"]
        rival = client.login("rival-coordinator@example.dev", "ORG-HIGHLAND")
        r = client.get(f"/api/v1/requests/{rid}", headers=rival)
        assert r.status_code == 404  # cross-tenant trace is invisible
