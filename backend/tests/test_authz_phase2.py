"""Phase II P0 security tests: the 10 required tenancy/identity cases, the
role matrix, production gating of dev auth, and OIDC verification (tested with
locally generated RSA keys — no external IdP needed to validate the code path).
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import identity as ident
from app.authz import (Role, Permission, role_has_permission, resolve_org_scope,
                      AuthorizationError)

COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"
AUD = "auditor@example.dev"
OBS = "observer@example.dev"
RIVAL_COORD = "rival-coordinator@example.dev"


class FakeIdentity:
    def __init__(self, scopes, platform_admin=False):
        self.scopes = scopes
        self.is_platform_admin = platform_admin
        self.user_id = "U1"
        self.email = "u@example.dev"
        self.jti = "j1"

    def role_in(self, org_id):
        for s in self.scopes:
            if s["org_id"] == org_id:
                return s["role"]
        return None

    def org_ids(self):
        return [s["org_id"] for s in self.scopes]


# ----------------------------------------------------------------------
# The 10 required cross-tenant / authorization cases (via API)
# ----------------------------------------------------------------------
class TestTenantIsolationAPI:
    def test_1_cannot_read_other_org_requests(self, client):
        h = client.login(COORD, org="ORG-PACIFIC")
        r = client.get("/api/v1/state", headers={
            "Authorization": h["Authorization"], "X-Org-Id": "ORG-HIGHLAND"})
        assert r.status_code == 403

    def test_2_cannot_update_other_org_inventory(self, client):
        # the only inventory-affecting writes are delivery + transitions
        h = client.login(VOL, org="ORG-PACIFIC")
        r = client.post("/api/v1/deliveries/confirm", headers={
            "Authorization": h["Authorization"], "X-Org-Id": "ORG-HIGHLAND"},
            json={"request_id": "REQ-001", "volunteer_name": "X"})
        assert r.status_code == 403

    def test_3_cannot_access_other_org_plan(self, client):
        h = client.login(COORD, org="ORG-PACIFIC")
        r = client.get("/api/v1/dispatch-queue", headers={
            "Authorization": h["Authorization"], "X-Org-Id": "ORG-HIGHLAND"})
        assert r.status_code == 403

    def test_4_cannot_confirm_other_org_delivery(self, client):
        h = client.login(VOL, org="ORG-PACIFIC")
        r = client.post("/api/v1/deliveries/confirm", headers={
            "Authorization": h["Authorization"], "X-Org-Id": "ORG-HIGHLAND"},
            json={"request_id": "REQ-001", "volunteer_name": "X"})
        assert r.status_code == 403

    def test_5_volunteer_cannot_approve(self, client):
        r = client.post("/api/v1/replan/approve", headers=client.login(VOL),
                        json={"approver_name": "V"})
        assert r.status_code == 403

    def test_6_auditor_cannot_modify(self, client):
        r = client.post("/api/v1/missions/transition", headers=client.login(AUD),
                        json={"request_id": "REQ-050", "new_status": "PLANNED",
                              "actor_id": "auditor"})
        assert r.status_code == 403

    def test_7_revoked_session_invalidated(self, client):
        h = client.login(OBS)
        r = client.post("/api/v1/auth/logout", headers=h)
        assert r.status_code == 200
        # the same token must now fail
        r = client.get("/api/v1/state", headers=h)
        assert r.status_code == 401

    def test_8_invalid_issuer_rejected(self, client):
        import jwt as pyjwt
        from app.main import DEV_ADAPTER
        now = int(time.time())
        bad = pyjwt.encode({"sub": "USR-x", "email": "x@x", "scopes": [],
                            "iss": "evil-issuer", "aud": ident.TOKEN_AUDIENCE,
                            "iat": now, "exp": now + 600, "jti": "j"},
                           DEV_ADAPTER.secret, algorithm="HS256")
        r = client.get("/api/v1/state", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401

    def test_9_incorrect_audience_rejected(self, client):
        import jwt as pyjwt
        from app.main import DEV_ADAPTER
        now = int(time.time())
        bad = pyjwt.encode({"sub": "USR-x", "email": "x@x", "scopes": [],
                            "iss": ident.TOKEN_ISSUER_DEV, "aud": "wrong-api",
                            "iat": now, "exp": now + 600, "jti": "j"},
                           DEV_ADAPTER.secret, algorithm="HS256")
        r = client.get("/api/v1/state", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401

    def test_10_missing_identity_fails_closed(self, client):
        for headers in [{}, {"X-Org-Id": "ORG-PACIFIC"},
                        {"Authorization": "Bearer garbage"}]:
            r = client.get("/api/v1/state", headers=headers)
            assert r.status_code == 401


class TestRoleMatrix:
    def test_auditor_and_observer_cannot_write(self):
        for role in (Role.AUDITOR, Role.READ_ONLY_OBSERVER):
            for perm in (Permission.CREATE_REQUEST, Permission.APPROVE_PLAN,
                         Permission.CONFIRM_DELIVERY, Permission.TRANSITION_MISSION,
                         Permission.MANAGE_MEMBERS):
                assert not role_has_permission(role.value, perm)

    def test_volunteer_permissions_minimal(self):
        assert role_has_permission(Role.FIELD_VOLUNTEER.value, Permission.CONFIRM_DELIVERY)
        assert not role_has_permission(Role.FIELD_VOLUNTEER.value, Permission.APPROVE_PLAN)
        assert not role_has_permission(Role.FIELD_VOLUNTEER.value, Permission.INJECT_DISRUPTION)

    def test_coordinator_can_plan_and_approve(self):
        assert role_has_permission(Role.MISSION_COORDINATOR.value, Permission.APPROVE_PLAN)
        assert role_has_permission(Role.MISSION_COORDINATOR.value, Permission.RUN_OPTIMIZATION)

    def test_unknown_role_fails_closed(self):
        assert not role_has_permission("SUPERUSER", Permission.READ_ORG_DATA)

    def test_org_scope_resolution(self):
        idn = FakeIdentity([{"org_id": "A", "role": "NGO_ADMIN"}])
        assert resolve_org_scope(idn, "A") == "A"
        assert resolve_org_scope(idn, None) == "A"
        with pytest.raises(AuthorizationError):
            resolve_org_scope(idn, "B")  # not my org


class TestDevAuthProductionGating:
    def test_dev_auth_disabled_in_production(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEV_AUTH_ENABLED", "1")
        assert ident.DevAdapter.enabled() is False

    def test_dev_auth_requires_explicit_flag(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("DEV_AUTH_ENABLED", raising=False)
        assert ident.DevAdapter.enabled() is False  # fail closed by default


class TestOidcVerification:
    """The production adapter path, verified with locally generated RSA keys."""

    @pytest.fixture(scope="class")
    def rsa_pair(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return key

    def _jwks_server(self, rsa_pair, monkeypatch):
        """Serve a minimal JWKS from a local HTTP server the adapter can fetch."""
        from cryptography.hazmat.primitives import serialization
        import base64, json, threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        pub = rsa_pair.public_key().public_numbers()
        def b64int(n):
            b = n.to_bytes((n.bit_length() + 7) // 8, "big")
            return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

        jwks = {"keys": [{"kty": "RSA", "alg": "RS256", "use": "sig", "kid": "k1",
                         "n": b64int(pub.n), "e": b64int(pub.e)}]}

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps(jwks).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{server.server_address[1]}/jwks.json"
        server.shutdown()

    def test_valid_rs256_token_accepted(self, rsa_pair, monkeypatch):
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        jwks_gen = self._jwks_server(rsa_pair, monkeypatch)
        jwks_url = next(jwks_gen)
        adapter = ident.ProductionAdapter(issuer="https://idp.test", audience="aidnexus-api",
                                           jwks_url=jwks_url, algorithms=["RS256"])
        now = int(time.time())
        token = pyjwt.encode({"sub": "USR-1", "iss": "https://idp.test",
                              "aud": "aidnexus-api", "iat": now, "exp": now + 600},
                             rsa_pair.private_bytes(serialization.Encoding.PEM,
                                                     serialization.PrivateFormat.PKCS8,
                                                     serialization.NoEncryption()),
                             algorithm="RS256", headers={"kid": "k1"})
        claims = adapter.verify_token(token)
        assert claims["sub"] == "USR-1"

    def test_wrong_issuer_rejected(self, rsa_pair, monkeypatch):
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        jwks_gen = self._jwks_server(rsa_pair, monkeypatch)
        jwks_url = next(jwks_gen)
        adapter = ident.ProductionAdapter(issuer="https://idp.test", audience="aidnexus-api",
                                          jwks_url=jwks_url, algorithms=["RS256"])
        now = int(time.time())
        token = pyjwt.encode({"sub": "USR-1", "iss": "https://evil.test",
                              "aud": "aidnexus-api", "iat": now, "exp": now + 600},
                             rsa_pair.private_bytes(serialization.Encoding.PEM,
                                                     serialization.PrivateFormat.PKCS8,
                                                     serialization.NoEncryption()),
                             algorithm="RS256", headers={"kid": "k1"})
        with pytest.raises(ident.IdentityError, match="issuer|token"):
            adapter.verify_token(token)

    def test_expired_token_rejected(self, rsa_pair, monkeypatch):
        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        jwks_gen = self._jwks_server(rsa_pair, monkeypatch)
        jwks_url = next(jwks_gen)
        adapter = ident.ProductionAdapter(issuer="https://idp.test", audience="aidnexus-api",
                                          jwks_url=jwks_url, algorithms=["RS256"])
        now = int(time.time())
        token = pyjwt.encode({"sub": "USR-1", "iss": "https://idp.test",
                              "aud": "aidnexus-api", "iat": now - 7200,
                              "exp": now - 3600},
                             rsa_pair.private_bytes(serialization.Encoding.PEM,
                                                     serialization.PrivateFormat.PKCS8,
                                                     serialization.NoEncryption()),
                             algorithm="RS256", headers={"kid": "k1"})
        with pytest.raises(ident.IdentityError, match="expired"):
            adapter.verify_token(token)
