"""Phase III implemented-feature tests (Wave 11 batch, P1 features).

Covers: INV-006 inventory expiry, VOL-011 certification expiry, APR-006
approval delegation (grant + revoke + tenant scope + holder-only delegation),
EVD-022 audit search, TRI-011 case notes. All via the authenticated API.
"""
from datetime import datetime, timedelta, timezone

COORD = "coordinator@example.dev"
ADMIN = "ngo-admin@example.dev"
VOL = "volunteer@example.dev"
AUD = "auditor@example.dev"
OBS = "observer@example.dev"


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class TestInventoryExpiry:
    def test_set_and_report_expiry(self, client):
        h = client.login(ADMIN)
        r = client.put("/api/v1/inventory/expiry", headers=h, json={
            "depot_id": "DEPOT-ALPHA", "item_type": "rations_mre",
            "expires_at": _iso(10)})
        assert r.status_code == 200 and r.json()["success"] is True
        r = client.get("/api/v1/inventory/expiring?within_days=30", headers=h)
        items = r.json()["items"]
        assert any(i["item_type"] == "rations_mre" and not i["already_expired"]
                   for i in items)
        # window filtering: far-future expiry not reported in 30 days
        client.put("/api/v1/inventory/expiry", headers=h, json={
            "depot_id": "DEPOT-ALPHA", "item_type": "generators",
            "expires_at": _iso(400)})
        r = client.get("/api/v1/inventory/expiring?within_days=30", headers=h)
        assert not any(i["item_type"] == "generators" for i in r.json()["items"])

    def test_already_expired_flagged(self, client):
        h = client.login(ADMIN)
        client.put("/api/v1/inventory/expiry", headers=h, json={
            "depot_id": "DEPOT-BRAVO", "item_type": "hygiene_kits",
            "expires_at": _iso(-1)})
        r = client.get("/api/v1/inventory/expiring", headers=h)
        item = next(i for i in r.json()["items"] if i["item_type"] == "hygiene_kits")
        assert item["already_expired"] is True

    def test_expiry_tenant_scoped(self, client):
        h = client.login(ADMIN)  # admin of both orgs; set in PACIFIC
        client.put("/api/v1/inventory/expiry", headers={
            "Authorization": h["Authorization"], "X-Org-Id": "ORG-PACIFIC"}, json={
            "depot_id": "DEPOT-ALPHA", "item_type": "trauma_kits",
            "expires_at": _iso(5)})
        hh = client.login("rival-admin@example.dev", org="ORG-HIGHLAND")
        r = client.get("/api/v1/inventory/expiring", headers=hh)
        assert not any(i["item_type"] == "trauma_kits" and
                       i["expires_at"].startswith(_iso(5)[:10]) for i in r.json()["items"])

    def test_volunteer_cannot_set_expiry(self, client):
        r = client.put("/api/v1/inventory/expiry", headers=client.login(VOL), json={
            "depot_id": "DEPOT-ALPHA", "item_type": "rations_mre",
            "expires_at": _iso(1)})
        assert r.status_code == 403


class TestCertificationExpiry:
    def test_set_and_report_expired_certification(self, client):
        h = client.login(ADMIN)
        r = client.put("/api/v1/volunteers/certification", headers=h, json={
            "volunteer_id": "VOL-03", "expires_at": _iso(-2)})
        assert r.status_code == 200
        r = client.get("/api/v1/volunteers/expired-certifications", headers=h)
        expired = r.json()["volunteers"]
        assert any(v["volunteer_id"] == "VOL-03" for v in expired)

    def test_valid_certification_not_reported(self, client):
        h = client.login(ADMIN)
        client.put("/api/v1/volunteers/certification", headers=h, json={
            "volunteer_id": "VOL-05", "expires_at": _iso(365)})
        r = client.get("/api/v1/volunteers/expired-certifications", headers=h)
        assert not any(v["volunteer_id"] == "VOL-05" for v in r.json()["volunteers"])


class TestApprovalDelegation:
    def test_delegation_grants_permission_temporarily(self, client):
        # observer cannot read audit normally (no AUDIT_READ)
        obs = client.login(OBS)
        assert client.get("/api/v1/audit", headers=obs).status_code == 403
        # admin delegates AUDIT_READ to the observer for 1 hour
        admin = client.login(ADMIN)
        r = client.post("/api/v1/delegations", headers=admin, json={
            "delegate_email": OBS, "permission": "AUDIT_READ", "hours": 1.0})
        assert r.status_code == 200
        # now the observer can read audit via delegation
        assert client.get("/api/v1/audit", headers=obs).status_code == 200

    def test_delegation_revocation_takes_effect(self, client):
        admin = client.login(ADMIN)
        client.post("/api/v1/delegations", headers=admin, json={
            "delegate_email": OBS, "permission": "AUDIT_READ", "hours": 1.0})
        obs = client.login(OBS)
        assert client.get("/api/v1/audit", headers=obs).status_code == 200
        r = client.post("/api/v1/delegations/revoke", headers=admin, json={
            "delegate_email": OBS, "permission": "AUDIT_READ", "hours": 1.0})
        assert r.status_code == 200 and r.json()["revoked"] >= 1
        assert client.get("/api/v1/audit", headers=obs).status_code == 403

    def test_only_holder_can_delegate(self, client):
        # the observer cannot delegate a permission they do not hold
        r = client.post("/api/v1/delegations", headers=client.login(OBS), json={
            "delegate_email": VOL, "permission": "AUDIT_READ", "hours": 1.0})
        assert r.status_code == 403

    def test_delegation_is_tenant_scoped(self, client):
        # delegation created in PACIFIC must not work for the HIGHLAND org
        admin = client.login(ADMIN)
        client.post("/api/v1/delegations", headers=admin, json={
            "delegate_email": OBS, "permission": "AUDIT_READ", "hours": 1.0})
        obs_h = {"Authorization": client.login(OBS)["Authorization"],
                 "X-Org-Id": "ORG-HIGHLAND"}
        r = client.get("/api/v1/audit", headers=obs_h)
        assert r.status_code == 403  # observer has no HIGHLAND membership at all


class TestAuditSearch:
    def test_filter_by_event_type_and_contains(self, client):
        h = client.login(AUD)
        r = client.get("/api/v1/audit?event_type=DELIVERY_CONFIRMED", headers=h)
        assert r.status_code == 200
        assert all(e["event_type"] == "DELIVERY_CONFIRMED" for e in r.json()["events"])
        r = client.get("/api/v1/audit?contains=bootstrap", headers=h)
        assert any("bootstrap" in e["summary"].lower() for e in r.json()["events"])
        # chain verification always present
        assert "chain_valid" in r.json()

    def test_audit_tenant_scoped_in_search(self, client):
        # the PACIFIC auditor has no HIGHLAND membership: fail closed
        h = {"Authorization": client.login(AUD)["Authorization"],
             "X-Org-Id": "ORG-HIGHLAND"}
        r = client.get("/api/v1/audit?contains=DEPOT-BRAVO", headers=h)
        assert r.status_code == 403


class TestCaseNotes:
    def test_add_and_list_notes_audited(self, client):
        h = client.login(COORD)
        q = client.get("/api/v1/state", headers=h).json()["dispatch_queue"]
        rid = q[0]["request_id"]
        r = client.post(f"/api/v1/missions/{rid}/notes", headers=h,
                        json={"note": "Contact verified by phone; household of 6."})
        assert r.status_code == 200
        note_id = r.json()["note"]["id"]
        r = client.get(f"/api/v1/missions/{rid}/notes", headers=h)
        notes = r.json()["notes"]
        assert any(n["id"] == note_id and
                   "household of 6" in n["note"] for n in notes)
        # audited
        aud = {"Authorization": client.login(AUD)["Authorization"], "X-Org-Id": "ORG-PACIFIC"}
        r = client.get("/api/v1/audit?event_type=CASE_NOTE_ADDED", headers=aud)
        assert any(e["entity_id"] == rid for e in r.json()["events"])

    def test_notes_tenant_scoped(self, client):
        """Both orgs use the same seed request ids; the isolation guarantee is
        that PACIFIC note CONTENT never appears under a HIGHLAND scope."""
        pacific_h = client.login(COORD)
        q = client.get("/api/v1/state", headers=pacific_h).json()["dispatch_queue"]
        rid = q[0]["request_id"]
        r = client.post(f"/api/v1/missions/{rid}/notes", headers=pacific_h,
                        json={"note": "PACIFIC-ONLY-CONFIDENTIAL-NOTE"})
        assert r.status_code == 200
        h = {"Authorization": client.login("rival-coordinator@example.dev")["Authorization"],
             "X-Org-Id": "ORG-HIGHLAND"}
        r = client.get(f"/api/v1/missions/{rid}/notes", headers=h)
        assert r.status_code == 200  # the id exists in HIGHLAND's own scenario
        assert all("PACIFIC-ONLY-CONFIDENTIAL-NOTE" not in n["note"]
                   for n in r.json()["notes"])  # but PACIFIC content never leaks

    def test_unknown_request_rejected(self, client):
        r = client.post("/api/v1/missions/NOPE/notes", headers=client.login(COORD),
                        json={"note": "x"})
        assert r.status_code == 404
