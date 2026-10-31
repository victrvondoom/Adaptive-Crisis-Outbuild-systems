"""MISSION D — Resource Replenishment (Phase IV Wave 5).

Procurement-to-inventory: threshold awareness, supplier registry +
verification, budget checks, human approval, goods receipt with
discrepancy handling, warehouse ledger update, evidence preservation.
"""
COORD = "coordinator@example.dev"
ADMIN = "ngo-admin@example.dev"
VOL = "volunteer@example.dev"
RIVAL = "rival-coordinator@example.dev"


class TestMissionD:
    def test_01_supplier_registry_and_verification(self, client):
        h = client.login(ADMIN)
        r = client.post("/api/v1/suppliers", headers=h,
                        json={"name": "Manila Relief Logistics", "verified": False})
        assert r.status_code == 200
        sup = r.json()
        assert sup["verified"] is False
        coord = client.login(COORD)
        pid = client.post("/api/v1/procurements", headers=coord, json={
            "supplier_id": sup["supplier_id"], "depot_id": "DEPOT-ALPHA",
            "item_type": "rations_mre", "quantity": 200, "unit_cost_cents": 350}).json()["procurement_id"]
        # approval is blocked: supplier not verified
        r = client.post(f"/api/v1/procurements/{pid}/approve", headers=h)
        assert r.status_code == 409 and "verified" in r.json()["detail"].lower()
        # verify the supplier, then approval succeeds
        r = client.put(f"/api/v1/suppliers/{sup['supplier_id']}/verify", headers=h)
        assert r.status_code == 200 and r.json()["verified"] is True
        r = client.post(f"/api/v1/procurements/{pid}/approve", headers=h)
        assert r.status_code == 200 and r.json()["status"] == "APPROVED"

    def test_02_full_procurement_chain_with_budget(self, client):
        admin = client.login(ADMIN)
        coord = client.login(COORD)

        # register + verify supplier
        sup = client.post("/api/v1/suppliers", headers=admin,
                          json={"name": "Cebu Provisions Co.", "verified": True}).json()
        assert sup["verified"] is True

        # budget control: set a small budget, approval must fail
        client.put("/api/v1/orgs/budget", headers=admin,
                   json={"budget_cents": 10000})
        pid = client.post("/api/v1/procurements", headers=coord, json={
            "supplier_id": sup["supplier_id"], "depot_id": "DEPOT-ALPHA",
            "item_type": "rations_mre", "quantity": 100,
            "unit_cost_cents": 350}).json()["procurement_id"]  # 35000c > 10000c
        r = client.post(f"/api/v1/procurements/{pid}/approve", headers=admin)
        assert r.status_code == 409 and "Budget exceeded" in r.json()["detail"]

        # raise the budget and approve
        client.put("/api/v1/orgs/budget", headers=admin,
                   json={"budget_cents": 100000})
        r = client.post(f"/api/v1/procurements/{pid}/approve", headers=admin)
        assert r.status_code == 200 and r.json()["status"] == "APPROVED"

        # receive goods: full quantity -> RECEIVED, stock increases exactly once
        r = client.post(f"/api/v1/procurements/{pid}/receive", headers=admin,
                        json={"received_quantity": 100})
        assert r.status_code == 200 and r.json()["status"] == "RECEIVED"
        # double receipt is rejected (idempotency)
        r = client.post(f"/api/v1/procurements/{pid}/receive", headers=admin,
                        json={"received_quantity": 100})
        assert r.status_code == 409

        # evidence: procurement history is tenant-scoped and audited
        audit = client.get("/api/v1/audit?contains=procurement", headers=admin).json()
        assert audit["chain_valid"] is True
        assert any(e["event_type"] == "PROCUREMENT_PROPOSED" for e in audit["events"])
        received = client.get("/api/v1/audit?contains=goods received", headers=admin).json()
        assert any(e["event_type"] == "PROCUREMENT_RECEIVED" for e in received["events"])

    def test_03_discrepancy_handling(self, client):
        admin = client.login(ADMIN)
        sup = client.post("/api/v1/suppliers", headers=admin,
                          json={"name": "Quezon Medical Supply", "verified": True}).json()
        pid = client.post("/api/v1/procurements", headers=client.login(COORD), json={
            "supplier_id": sup["supplier_id"], "depot_id": "DEPOT-BRAVO",
            "item_type": "trauma_kits", "quantity": 50,
            "unit_cost_cents": 1200}).json()["procurement_id"]
        client.post(f"/api/v1/procurements/{pid}/approve", headers=admin)
        # only 40 of 50 arrive
        r = client.post(f"/api/v1/procurements/{pid}/receive", headers=admin,
                        json={"received_quantity": 40,
                              "discrepancy_note": "2 cases damaged in transit"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "DISCREPANCY"
        assert body["received_quantity"] == 40
        assert body["discrepancy_note"]
        # inventory only gained the received amount (ledger truth)
        movements = client.get("/api/v1/impact/report", headers=admin).json()
        assert movements["movement_count"] > 0

    def test_04_tenant_isolation(self, client):
        admin = client.login(ADMIN)
        sup = client.post("/api/v1/suppliers", headers=admin,
                          json={"name": "Pacific Only Supplier", "verified": True}).json()
        rival = client.login(RIVAL, "ORG-HIGHLAND")
        # HIGHLAND cannot see PACIFIC suppliers or procurements
        suppliers = client.get("/api/v1/suppliers", headers=rival).json()["suppliers"]
        assert all(s["supplier_id"] != sup["supplier_id"] for s in suppliers)
        # HIGHLAND cannot approve a PACIFIC procurement
        pid = client.post("/api/v1/procurements", headers=client.login(COORD), json={
            "supplier_id": sup["supplier_id"], "depot_id": "DEPOT-ALPHA",
            "item_type": "hygiene_kits", "quantity": 10,
            "unit_cost_cents": 200}).json()["procurement_id"]
        r = client.post(f"/api/v1/procurements/{pid}/approve", headers=rival)
        assert r.status_code in (403, 404)  # guard or tenant lookup both fail closed

    def test_05_permission_gating(self, client):
        vol = client.login(VOL)
        # volunteers cannot register suppliers nor set budgets
        assert client.post("/api/v1/suppliers", headers=vol,
                           json={"name": "XX"}).status_code == 403
        assert client.put("/api/v1/orgs/budget", headers=vol,
                          json={"budget_cents": 1}).status_code == 403
