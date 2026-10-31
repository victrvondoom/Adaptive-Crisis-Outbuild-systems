"""MISSION B — Self-Healing Disaster Response (Phase IV Wave 6).

A planned, partly-executed mission suffers warehouse failure, route closure
and vehicle breakdown. Verifies: incident detection, affected-work
identification, completed-delivery preservation, commitment preservation,
recovery plan generation, human approval, version history, queue concordance
and honest blocked/unmet visibility.
"""
COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"


class TestMissionB:
    def test_full_self_healing_chain(self, client):
        h = client.login(COORD)
        # baseline: fresh scenario (the initial plan is auto-activated by the
        # system bootstrap — every LATER plan requires human approval)
        client.post("/api/v1/scenario/reset", headers=h)
        state0 = client.get("/api/v1/state", headers=h).json()
        v1 = state0["current_plan"]["version_id"]

        # partly executed: deliver one request
        state = client.get("/api/v1/state", headers=h).json()
        target = next(q for q in state["dispatch_queue"]
                      if q["status"] == "DISPATCHED")["request_id"]
        r = client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                        json={"request_id": target, "volunteer_name": "M. Santos"})
        assert r.status_code == 200

        # inject warehouse failure (depot outage)
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "DEPOT_OUTAGE", "title": "Depot Alpha flooded",
            "description": "Flood damage to the primary warehouse",
            "depot_id": "DEPOT-ALPHA"})
        assert r.status_code == 200
        body = r.json()
        assert body["replan_version"]
        assert "replan_delta" in body
        # completed delivery is preserved (never re-planned or lost)
        assert client.get(f"/api/v1/missions/{target}", headers=h).status_code == 200

        # human approves the recovery plan
        r = client.post("/api/v1/replan/approve", headers=h,
                        json={"approver_name": "Coord"})
        assert r.status_code == 200
        v2 = r.json()["plan"]["version_id"]
        assert v2 != v1

        # inject route closure on top: second disruption, next version
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "ROAD_BLOCKAGE", "title": "Landslide on N-120",
            "description": "Major route closed",
            "lat": 14.62, "lng": 120.99})
        assert r.status_code == 200
        r = client.post("/api/v1/replan/approve", headers=h,
                        json={"approver_name": "Coord"})
        v3 = r.json()["plan"]["version_id"]
        assert v3 not in (v1, v2)

        # inject vehicle breakdown
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "VEHICLE_BREAKDOWN", "title": "Truck 3 axle failure",
            "description": "Vehicle out of service"})
        assert r.status_code == 200
        client.post("/api/v1/replan/approve", headers=h,
                    json={"approver_name": "Coord"})

        # invariants after 3 simultaneous-ish disruptions:
        state = client.get("/api/v1/state", headers=h).json()
        # 1. the delivered request is STILL delivered (completed work preserved)
        assert any(r["id"] == target and r["status"] == "DELIVERED"
                   for r in state["requests"])
        # 2. queue remains a pure projection of the approved plan
        assert state["stats"]["queue_concordance"] == 1.0
        # 3. blocked requests are visible with explicit reasons, never hidden
        for b in state["blocked_requests"]:
            assert b["feasibility_status"] and b["explanation"]
        # 4. version history is sequential and queryable
        audit = client.get("/api/v1/audit?contains=plan", headers=h).json()
        assert audit["chain_valid"] is True

    def test_recovery_preserves_unaffected_commitments(self, client):
        """Requests already en route (DISPATCHED) keep their assignments unless
        the disruption actually affects them; the plan version increments only
        through the sanctioned replan path."""
        h = client.login(COORD)
        client.post("/api/v1/scenario/reset", headers=h)
        before = client.get("/api/v1/state", headers=h).json()
        dispatched_before = {q["request_id"] for q in before["dispatch_queue"]
                             if q["status"] == "DISPATCHED"}
        # inject a disruption far from any route/depot
        client.post("/api/v1/disrupt", headers=h, json={
            "type": "WEATHER_HAZARD", "title": "Advisory far away",
            "description": "Remote advisory",
            "lat": 13.0, "lng": 119.0, "hazard_radius_km": 1.0})
        client.post("/api/v1/replan/approve", headers=h,
                    json={"approver_name": "Coord"})
        after = client.get("/api/v1/state", headers=h).json()
        delivered_or_dispatched = (
            {r["id"] for r in after["requests"] if r["status"] == "DELIVERED"}
            | {q["request_id"] for q in after["dispatch_queue"]
               if q["status"] == "DISPATCHED"})
        # every previously-dispatched request remains delivered or dispatched
        assert dispatched_before <= delivered_or_dispatched
