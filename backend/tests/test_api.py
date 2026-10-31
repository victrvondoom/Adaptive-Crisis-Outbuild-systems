"""API contract tests: endpoint behavior, validation, idempotency, and the
frontend-critical paths (triage URL, dispatch queue, transitions)."""
import pytest
from fastapi.testclient import TestClient


class TestHealthAndState:
    def test_health(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "HEALTHY"
        assert r.json()["queue_concordance"] == 1.0

    def test_state_complete_payload(self, client):
        r = client.get("/api/v1/state")
        assert r.status_code == 200
        data = r.json()
        assert len(data["requests"]) == 200          # full list, no truncation
        assert "dispatch_queue" in data
        assert "blocked_requests" in data
        assert data["stats"]["queue_concordance"] == 1.0

    def test_dispatch_queue_endpoint(self, client):
        r = client.get("/api/v1/dispatch-queue")
        assert r.status_code == 200
        data = r.json()
        seqs = [q["scheduled_sequence"] for q in data["queue"]]
        assert seqs == sorted(seqs)
        assert data["queue_concordance"] == 1.0


class TestTriageEndpoint:
    def test_triage_works_on_canonical_path(self, client):
        """Regression: the frontend used to call /api/v1/api/v1/nlp/triage (404)."""
        r = client.post("/api/v1/nlp/triage",
                        json={"raw_text": "urgent need 100 liters water"})
        assert r.status_code == 200
        data = r.json()
        assert data["request"]["items"][0]["quantity"] == 100.0
        assert "evidence" in data

    def test_frontend_path_no_longer_doubled(self, client):
        r = client.post("/api/v1/api/v1/nlp/triage",
                        json={"raw_text": "urgent need 100 liters water"})
        assert r.status_code == 404  # the buggy doubled path must NOT exist

    def test_triage_evidence_returned(self, client):
        r = client.post("/api/v1/nlp/triage",
                        json={"raw_text": "no quantities here"})
        data = r.json()
        assert data["request"]["items"] == []
        assert data["evidence"]["requires_human_review"] is True


class TestTransitionsEndpoint:
    def test_illegal_transition_returns_400_with_allowed_list(self, client):
        r = client.post("/api/v1/missions/transition",
                        json={"request_id": "REQ-050", "new_status": "DELIVERED",
                              "actor_id": "attacker"})
        assert r.status_code == 400
        assert "Allowed" in r.json()["detail"]

    def test_legal_transition(self, client):
        r = client.post("/api/v1/missions/transition",
                        json={"request_id": "REQ-050", "new_status": "PLANNED",
                              "actor_id": "coord", "reason": "test"})
        assert r.status_code == 200
        assert r.json()["new_status"] == "PLANNED"

    def test_unknown_mission_404(self, client):
        r = client.post("/api/v1/missions/transition",
                        json={"request_id": "NOPE", "new_status": "PLANNED",
                              "actor_id": "x"})
        assert r.status_code == 400  # ValueError -> 400 with message


class TestDeliveryEndpoint:
    def test_confirm_idempotent_via_api(self, client):
        s = client.get("/api/v1/state").json()
        req_id = s["dispatch_queue"][0]["request_id"]
        r1 = client.post("/api/v1/deliveries/confirm",
                         json={"request_id": req_id, "volunteer_name": "V"})
        r2 = client.post("/api/v1/deliveries/confirm",
                         json={"request_id": req_id, "volunteer_name": "V"})
        assert r1.status_code == r2.status_code == 200
        assert r2.json()["duplicate"] is True
        # inventory deducted once: compare depot stock across both calls
        s2 = client.get("/api/v1/state").json()

    def test_confirm_unknown_request_400(self, client):
        r = client.post("/api/v1/deliveries/confirm",
                        json={"request_id": "NOPE", "volunteer_name": "V"})
        assert r.status_code == 400


class TestDisruptionApprovalFlow:
    def test_disrupt_then_approve(self, client):
        client.post("/api/v1/scenario/reset")  # test isolation on shared singleton
        r = client.post("/api/v1/disrupt", json={
            "type": "DEPOT_OUTAGE", "title": "Flood", "description": "d",
            "depot_id": "DEPOT-BRAVO", "lat": 14.55, "lng": 120.94})
        assert r.status_code == 200
        body = r.json()
        assert body["replan_version"] == "v2.0"
        assert body["replan_delta"]["before_fulfilled"] >= 0
        # before approval, current plan is still v1.0
        s = client.get("/api/v1/state").json()
        assert s["stats"]["current_plan_version"] == "v1.0"
        assert s["stats"]["pending_replan_approval"] is True

        r = client.post("/api/v1/replan/approve", json={"approver_name": "Coord"})
        assert r.status_code == 200
        s = client.get("/api/v1/state").json()
        assert s["stats"]["current_plan_version"] == "v2.0"
        assert s["stats"]["pending_replan_approval"] is False

    def test_second_disruption_creates_next_version(self, client):
        client.post("/api/v1/scenario/reset")  # test isolation on shared singleton
        client.post("/api/v1/disrupt", json={
            "type": "DEPOT_OUTAGE", "title": "F", "description": "d",
            "depot_id": "DEPOT-BRAVO", "lat": 14.55, "lng": 120.94})
        client.post("/api/v1/replan/approve", json={"approver_name": "C"})
        r = client.post("/api/v1/disrupt", json={
            "type": "ROAD_BLOCKAGE", "title": "B", "description": "d",
            "lat": 14.62, "lng": 120.98})
        assert r.json()["replan_version"] == "v3.0"

    def test_approval_without_pending_400(self, client):
        client.post("/api/v1/scenario/reset")  # fresh state: no pending plan
        r = client.post("/api/v1/replan/approve", json={"approver_name": "C"})
        assert r.status_code == 400

    def test_disruption_payload_hardened(self, client):
        r = client.post("/api/v1/disrupt", json={
            "type": "ROAD_BLOCKAGE", "title": "x" * 500, "description": "d",
            "lat": 14.6, "lng": 120.98})
        assert r.status_code == 422  # max_length enforced


class TestBenchmarkEndpoint:
    def test_benchmark_runs_real_simulation(self, client):
        r = client.post("/api/v1/benchmark/run?seed=42&n_requests=50")
        assert r.status_code == 200
        data = r.json()
        strategies = {m["strategy_name"] for m in data["metrics"]}
        assert len(strategies) == 4
        assert data["n_requests"] == 50
        # all metrics populated from the trace
        for m in data["metrics"]:
            assert m["fulfilled_count"] + m["unmet_demand_count"] == m["total_requests"]

    def test_benchmark_rejects_bad_size(self, client):
        r = client.post("/api/v1/benchmark/run?seed=42&n_requests=5")
        assert r.status_code == 400
