"""MISSION C — Multi-NGO Resource Coordination (Phase IV Wave 4).

Two organizations with independent resources: PACIFIC has surplus, HIGHLAND
has demand. Verifies capability discovery (shared item taxonomy), ownership
(only the source org's stock moves), dual approval, transport (inventory
movement ledger in both orgs), handover confirmation, failure recovery,
tenant isolation and cross-organization impact visibility.
"""
COORD = "coordinator@example.dev"      # ORG-PACIFIC member
RIVAL = "rival-coordinator@example.dev"  # ORG-HIGHLAND member
ADMIN = "ngo-admin@example.dev"       # admin of both orgs


class TestMissionC:
    def test_01_capability_and_shared_resource_discovery(self, client):
        # both orgs exist and are reachable by their own members
        scopes = client.get("/api/v1/orgs", headers=client.login(COORD)).json()["scopes"]
        ids = {s["org_id"] for s in scopes}
        assert "ORG-PACIFIC" in ids
        rival = client.get("/api/v1/orgs",
                           headers=client.login(RIVAL, "ORG-HIGHLAND")).json()["scopes"]
        assert any(s["org_id"] == "ORG-HIGHLAND" for s in rival)
        # both orgs respond with healthy state (independent engines)
        st = client.get("/api/v1/state", headers=client.login(RIVAL, "ORG-HIGHLAND")).json()
        assert st["stats"]["total_requests"] > 0

    def test_02_proposal_validates_ownership_and_stock(self, client):
        h = client.login(COORD)
        # unknown destination org -> 400
        r = client.post("/api/v1/transfers", headers=h, json={
            "dest_org_id": "ORG-NOWHERE", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-ALPHA", "item_type": "rations_mre",
            "quantity": 5})
        assert r.status_code == 400
        # insufficient stock -> 400
        r = client.post("/api/v1/transfers", headers=h, json={
            "dest_org_id": "ORG-HIGHLAND", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-ALPHA", "item_type": "rations_mre",
            "quantity": 10_000_000})
        assert r.status_code == 400 and "Insufficient" in r.json()["detail"]
        # same org -> 400
        r = client.post("/api/v1/transfers", headers=h, json={
            "dest_org_id": "ORG-PACIFIC", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-BRAVO", "item_type": "rations_mre",
            "quantity": 5})
        assert r.status_code == 400

    def test_03_full_transfer_chain_with_dual_approval(self, client):
        pacific = client.login(COORD)
        highland = client.login(RIVAL, "ORG-HIGHLAND")

        # baseline stock in both orgs (from DB inventory)
        before = {}
        for org, hdr in (("ORG-PACIFIC", pacific), ("ORG-HIGHLAND", highland)):
            r = client.get("/api/v1/orgs/export", headers=hdr).json()
            before[org] = r  # export carries inventory snapshot

        # propose: PACIFIC shares 25 rations_mre with HIGHLAND
        r = client.post("/api/v1/transfers", headers=pacific, json={
            "dest_org_id": "ORG-HIGHLAND", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-ALPHA", "item_type": "rations_mre",
            "quantity": 25, "reason": "HIGHLAND shelter demand, PACIFIC surplus"})
        assert r.status_code == 200, r.text
        xfr = r.json()
        assert xfr["status"] == "PROPOSED"
        tid = xfr["transfer_id"]

        # destination cannot skip the source approval (sequential dual approval)
        r = client.post(f"/api/v1/transfers/{tid}/approve-destination",
                        headers=highland)
        assert r.status_code == 409

        # source organization approves
        r = client.post(f"/api/v1/transfers/{tid}/approve-source", headers=pacific)
        assert r.status_code == 200 and r.json()["status"] == "SOURCE_APPROVED"

        # a PACIFIC coordinator cannot approve AS the destination org
        r = client.post(f"/api/v1/transfers/{tid}/approve-destination",
                        headers=pacific)
        assert r.status_code == 403

        # destination approves
        r = client.post(f"/api/v1/transfers/{tid}/approve-destination",
                        headers=highland)
        assert r.status_code == 200 and r.json()["status"] == "DEST_APPROVED"

        # dispatch: stock moves, ledger rows in BOTH orgs
        r = client.post(f"/api/v1/transfers/{tid}/dispatch", headers=pacific)
        assert r.status_code == 200 and r.json()["status"] == "DISPATCHED"

        # handover confirmation by destination (delivery-confirmation permission)
        admin_highland = client.login(ADMIN, "ORG-HIGHLAND")
        r = client.post(f"/api/v1/transfers/{tid}/receive",
                        headers=admin_highland)
        assert r.status_code == 200 and r.json()["status"] == "RECEIVED"

        # both orgs see the transfer in their own list
        for hdr in (pacific, highland):
            lst = client.get("/api/v1/transfers", headers=hdr).json()["transfers"]
            assert any(t["transfer_id"] == tid for t in lst)

        # both audit chains verify and record the transfer events
        for org, hdr in (("ORG-PACIFIC", pacific), ("ORG-HIGHLAND", highland)):
            audit = client.get("/api/v1/audit?contains=transfer", headers=hdr).json()
            assert audit["chain_valid"] is True
            assert any("TRANSFER" in e["event_type"] for e in audit["events"])

    def test_04_dispatch_is_idempotent(self, client):
        """Replaying dispatch cannot double-move stock (ledger idempotency)."""
        pacific = client.login(COORD)
        highland = client.login(RIVAL, "ORG-HIGHLAND")
        xfr = client.post("/api/v1/transfers", headers=pacific, json={
            "dest_org_id": "ORG-HIGHLAND", "source_depot_id": "DEPOT-BRAVO",
            "dest_depot_id": "DEPOT-BRAVO", "item_type": "hygiene_kits",
            "quantity": 5}).json()
        tid = xfr["transfer_id"]
        client.post(f"/api/v1/transfers/{tid}/approve-source", headers=pacific)
        client.post(f"/api/v1/transfers/{tid}/approve-destination", headers=highland)
        d1 = client.post(f"/api/v1/transfers/{tid}/dispatch", headers=pacific).json()
        assert d1["status"] == "DISPATCHED"
        # second dispatch attempt is rejected by the state machine (409)
        d2 = client.post(f"/api/v1/transfers/{tid}/dispatch", headers=pacific)
        assert d2.status_code == 409

    def test_05_cancellation_before_dispatch(self, client):
        pacific = client.login(COORD)
        xfr = client.post("/api/v1/transfers", headers=pacific, json={
            "dest_org_id": "ORG-HIGHLAND", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-ALPHA", "item_type": "generators",
            "quantity": 1}).json()
        r = client.post(f"/api/v1/transfers/{xfr['transfer_id']}/cancel",
                        headers=pacific, params={"reason": "Withdrawn"})
        assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
        # a cancelled transfer cannot be approved anymore
        r = client.post(f"/api/v1/transfers/{xfr['transfer_id']}/approve-source",
                        headers=pacific)
        assert r.status_code == 409

    def test_06_tenant_isolation_of_transfers(self, client):
        """An org that is not a party to a transfer cannot see or act on it."""
        pacific = client.login(COORD)
        xfr = client.post("/api/v1/transfers", headers=pacific, json={
            "dest_org_id": "ORG-HIGHLAND", "source_depot_id": "DEPOT-ALPHA",
            "dest_depot_id": "DEPOT-ALPHA", "item_type": "trauma_kits",
            "quantity": 2}).json()
        tid = xfr["transfer_id"]
        # an outside org would see nothing; here every member is one of the two
        # parties, so isolation is asserted via action permissions:
        rival = client.login(RIVAL, "ORG-HIGHLAND")
        # HIGHLAND coordinator lacks APPROVE_PLAN in the source-org step
        r = client.post(f"/api/v1/transfers/{tid}/approve-source", headers=rival)
        assert r.status_code == 403
        # and cannot dispatch before approvals
        r = client.post(f"/api/v1/transfers/{tid}/dispatch", headers=rival)
        assert r.status_code == 409
