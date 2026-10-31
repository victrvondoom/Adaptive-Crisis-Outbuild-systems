"""Event-driven reliability (Phase IV Wave 9): transactional outbox consumer.

A committed business transaction must not lose its operational event; a
repeated dispatch must not create a second side effect. Honest semantics: no
external provider exists, so 'processing' marks delivery state for
observability — nothing is claimed as externally delivered.
"""
COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"


class TestOutboxDispatch:
    def test_intake_enqueues_event_and_dispatch_processes_it(self, client):
        h = client.login(COORD)
        intake = client.post("/api/v1/requests", headers=h, json={
            "requester_name": "Outbox Test Shelter",
            "lat": 14.6042, "lng": 120.9846, "sector": "Central Metro",
            "items": [{"item_type": "hygiene_kits", "quantity": 5, "unit": "kits"}],
            "priority": "MEDIUM",
            "consent": {"granted": True, "scope": "ASSISTANCE"}}).json()
        rid = intake["request"]["id"]
        # the intake committed an AidRequestCreated outbox event
        r = client.post("/api/v1/outbox/dispatch", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1
        assert any(e["event_type"] == "AidRequestCreated"
                   and e["org_id"] == "ORG-PACIFIC" for e in body["processed"])

    def test_dispatch_is_idempotent_no_double_processing(self, client):
        h = client.login(COORD)
        first = client.post("/api/v1/outbox/dispatch", headers=h).json()
        assert first["count"] >= 0
        # second run: everything already processed -> nothing re-processed
        second = client.post("/api/v1/outbox/dispatch", headers=h).json()
        processed_ids_first = {e["outbox_id"] for e in first["processed"]}
        processed_ids_second = {e["outbox_id"] for e in second["processed"]}
        assert not (processed_ids_first & processed_ids_second)

    def test_permission_gated(self, client):
        vol = client.login(VOL)
        assert client.post("/api/v1/outbox/dispatch", headers=vol).status_code == 403
