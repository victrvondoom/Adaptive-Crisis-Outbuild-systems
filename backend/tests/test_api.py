"""API contract tests (Phase II: authenticated, tenant-scoped)."""
import pytest

COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"
AUD = "auditor@example.dev"
RIVAL = "rival-coordinator@example.dev"


class TestHealthAndState:
    def test_health(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "HEALTHY"

    def test_readyz(self, client):
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

    def test_state_requires_auth(self, client):
        assert client.get("/api/v1/state").status_code == 401  # fail closed

    def test_state_complete_payload(self, client):
        r = client.get("/api/v1/state", headers=client.login(COORD))
        assert r.status_code == 200
        data = r.json()
        assert len(data["requests"]) == 200
        assert "dispatch_queue" in data and "blocked_requests" in data
        assert data["stats"]["queue_concordance"] == 1.0

    def test_dispatch_queue_endpoint(self, client):
        r = client.get("/api/v1/dispatch-queue", headers=client.login(COORD))
        seqs = [q["scheduled_sequence"] for q in r.json()["queue"]]
        assert seqs == sorted(seqs)
        assert r.json()["queue_concordance"] == 1.0


class TestTriageEndpoint:
    def test_triage_works_on_canonical_path(self, client):
        r = client.post("/api/v1/nlp/triage", headers=client.login(COORD),
                        json={"raw_text": "urgent need 100 liters water"})
        assert r.status_code == 200
        data = r.json()
        assert data["request"]["items"][0]["quantity"] == 100.0
        assert "evidence" in data

    def test_frontend_path_no_longer_doubled(self, client):
        r = client.post("/api/v1/api/v1/nlp/triage", headers=client.login(COORD),
                        json={"raw_text": "urgent need 100 liters water"})
        assert r.status_code == 404

    def test_triage_persists_request(self, client):
        r = client.post("/api/v1/nlp/triage", headers=client.login(COORD),
                        json={"raw_text": "urgent need 100 liters water"})
        rid = r.json()["request"]["id"]
        r2 = client.get(f"/api/v1/missions/{rid}", headers=client.login(COORD))
        assert r2.status_code == 200


class TestTransitionsEndpoint:
    def test_illegal_transition_returns_400(self, client):
        r = client.post("/api/v1/missions/transition", headers=client.login(COORD),
                        json={"request_id": "REQ-050", "new_status": "DELIVERED",
                              "actor_id": "attacker"})
        assert r.status_code == 400
        assert "Allowed" in r.json()["detail"]

    def test_legal_transition(self, client):
        r = client.post("/api/v1/missions/transition", headers=client.login(COORD),
                        json={"request_id": "REQ-050", "new_status": "PLANNED",
                              "actor_id": "coord", "reason": "test"})
        assert r.status_code == 200


class TestDeliveryEndpoint:
    def test_confirm_idempotent_via_api(self, client):
        h = client.login(VOL)
        q = client.get("/api/v1/state", headers=client.login(COORD)).json()["dispatch_queue"]
        req_id = next(x for x in q if x["status"] == "DISPATCHED")["request_id"]
        r1 = client.post("/api/v1/deliveries/confirm", headers=h,
                         json={"request_id": req_id, "volunteer_name": "V"})
        r2 = client.post("/api/v1/deliveries/confirm", headers=h,
                         json={"request_id": req_id, "volunteer_name": "V"})
        assert r1.status_code == r2.status_code == 200
        assert r2.json()["duplicate"] is True

    def test_confirm_unknown_request_400(self, client):
        r = client.post("/api/v1/deliveries/confirm", headers=client.login(VOL),
                        json={"request_id": "NOPE", "volunteer_name": "V"})
        assert r.status_code == 400


class TestDisruptionApprovalFlow:
    def test_disrupt_then_approve(self, client):
        h = client.login(COORD)
        client.post("/api/v1/scenario/reset", headers=h)
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "DEPOT_OUTAGE", "title": "Flood", "description": "d",
            "depot_id": "DEPOT-BRAVO", "lat": 14.55, "lng": 120.94})
        assert r.status_code == 200
        assert r.json()["replan_version"] == "v2.0"
        s = client.get("/api/v1/state", headers=h).json()
        assert s["stats"]["current_plan_version"] == "v1.0"
        assert s["stats"]["pending_replan_approval"] is True
        r = client.post("/api/v1/replan/approve", headers=h, json={"approver_name": "Coord"})
        assert r.status_code == 200
        s = client.get("/api/v1/state", headers=h).json()
        assert s["stats"]["current_plan_version"] == "v2.0"

    def test_second_disruption_creates_next_version(self, client):
        h = client.login(COORD)
        client.post("/api/v1/scenario/reset", headers=h)
        client.post("/api/v1/disrupt", headers=h, json={
            "type": "DEPOT_OUTAGE", "title": "F", "description": "d",
            "depot_id": "DEPOT-BRAVO", "lat": 14.55, "lng": 120.94})
        client.post("/api/v1/replan/approve", headers=h, json={"approver_name": "C"})
        r = client.post("/api/v1/disrupt", headers=h, json={
            "type": "ROAD_BLOCKAGE", "title": "B", "description": "d",
            "lat": 14.62, "lng": 120.98})
        assert r.json()["replan_version"] == "v3.0"

    def test_approval_without_pending_400(self, client):
        h = client.login(COORD)
        client.post("/api/v1/scenario/reset", headers=h)
        r = client.post("/api/v1/replan/approve", headers=h, json={"approver_name": "C"})
        assert r.status_code == 400

    def test_disruption_payload_hardened(self, client):
        r = client.post("/api/v1/disrupt", headers=client.login(COORD), json={
            "type": "ROAD_BLOCKAGE", "title": "x" * 500, "description": "d",
            "lat": 14.6, "lng": 120.98})
        assert r.status_code == 422


class TestBenchmarkEndpoint:
    def test_benchmark_runs_real_simulation(self, client):
        r = client.post("/api/v1/benchmark/run?seed=42&n_requests=50",
                        headers=client.login(COORD))
        assert r.status_code == 200
        data = r.json()
        assert len({m["strategy_name"] for m in data["metrics"]}) == 4
        for m in data["metrics"]:
            assert m["fulfilled_count"] + m["unmet_demand_count"] == m["total_requests"]

    def test_benchmark_rejects_bad_size(self, client):
        r = client.post("/api/v1/benchmark/run?seed=42&n_requests=5",
                        headers=client.login(COORD))
        assert r.status_code == 400
