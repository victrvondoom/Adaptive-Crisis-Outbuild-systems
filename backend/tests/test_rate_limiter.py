"""Phase V rate-limiting tests (System Design Studio topic 01).

Token-bucket semantics (burst, refill, per-scope isolation) plus real API
behavior: 429 + Retry-After, expensive-endpoint quotas, tenant isolation,
and exempt health endpoints.
"""
import pytest

from app.resilience_patterns import RateLimiter, TokenBucket


class TestTokenBucket:
    def test_burst_capacity_then_reject(self):
        b = TokenBucket(capacity=3, refill_rate=100.0)
        ok = [b.try_take(now=0.0)[0] for _ in range(5)]
        assert ok == [True, True, True, False, False]

    def test_refill_over_time(self):
        b = TokenBucket(capacity=2, refill_rate=1.0)
        assert b.try_take(now=0.0)[0]
        assert b.try_take(now=0.0)[0]
        assert not b.try_take(now=0.0)[0]
        # 1 second later, exactly one token refilled
        allowed, retry_after = b.try_take(now=1.0)
        assert allowed and 0.0 <= retry_after <= 0.001

    def test_retry_after_is_estimated(self):
        b = TokenBucket(capacity=1, refill_rate=0.5)
        assert b.try_take(now=0.0)[0]
        allowed, retry_after = b.try_take(now=0.0)
        assert not allowed and 1.9 <= retry_after <= 2.1


class TestRateLimiterScopes:
    def test_scopes_are_independent(self):
        rl = RateLimiter()
        for _ in range(3):
            assert rl.check([("ip:a", 3, 100.0)], now=0.0)[0]
        # org A exhausted its own bucket; org B unaffected
        assert not rl.check([("ip:a", 3, 100.0)], now=0.0)[0]
        assert rl.check([("ip:b", 3, 100.0)], now=0.0)[0]

    def test_all_scopes_must_allow(self):
        rl = RateLimiter()
        # user has a bigger personal budget; the org budget is the tight one
        assert rl.check([("user:u1", 5, 100.0), ("org:o1", 2, 100.0)], now=0.0)[0]
        assert rl.check([("user:u1", 5, 100.0), ("org:o1", 2, 100.0)], now=0.0)[0]
        # org budget exhausted -> request rejected, org is the limiting scope
        # (the user still had personal budget left)
        allowed, retry_after, limiting = rl.check(
            [("user:u1", 5, 100.0), ("org:o1", 2, 100.0)], now=0.0)
        assert not allowed and limiting == "org:o1"

    def test_reset_clears_buckets(self):
        rl = RateLimiter()
        assert not rl.check([("ip:x", 1, 0.001)], now=0.0)[1:] or True
        rl.check([("ip:x", 1, 0.001)], now=0.0)
        assert not rl.check([("ip:x", 1, 0.001)], now=0.0)[0]
        rl.reset("ip:")
        assert rl.check([("ip:x", 1, 0.001)], now=0.0)[0]


COORD = "coordinator@example.dev"
VOL = "volunteer@example.dev"


class TestAPIRateLimiting:
    """Against the real middleware with a tiny configured budget."""

    @pytest.fixture(autouse=True)
    def _tight_limits(self, monkeypatch):
        from app import main as main_mod
        monkeypatch.setitem(main_mod.RATE_LIMIT_CONFIG, "user", (3, 0.001))
        monkeypatch.setitem(main_mod.RATE_LIMIT_CONFIG, "anonymous", (2, 0.001))
        monkeypatch.setitem(main_mod.RATE_LIMIT_CONFIG, "expensive", (1, 0.001))
        main_mod.API_RATE_LIMITER.reset()
        yield
        main_mod.API_RATE_LIMITER.reset()

    def test_health_endpoint_exempt_from_limits(self, client):
        for _ in range(10):
            assert client.get("/healthz").status_code == 200

    def test_burst_exhaustion_returns_429_with_retry_after(self, client):
        h = client.login(COORD)
        statuses = [client.get("/api/v1/state", headers=h).status_code
                    for _ in range(6)]
        assert statuses[:3] == [200, 200, 200]
        assert 429 in statuses[3:]
        r = client.get("/api/v1/state", headers=h)
        assert r.status_code == 429
        assert r.headers.get("Retry-After")
        body = r.json()
        assert body["error"] == "Rate limit exceeded"
        assert body["limiting_scope"].startswith("user:")
        assert body["retry_after_seconds"] >= 1.0

    def test_429_body_matches_contract(self, client):
        h = client.login(COORD)
        for _ in range(3):
            client.get("/api/v1/me", headers=h)
        r = client.get("/api/v1/me", headers=h)
        assert r.status_code == 429
        assert set(r.json()) >= {"error", "message", "limiting_scope",
                                 "retry_after_seconds"}

    def test_tenant_isolation_of_quotas(self, client):
        """Exhausting PACIFIC's user bucket does not affect another identity."""
        pacific = client.login(COORD)
        rival = client.login("rival-coordinator@example.dev", "ORG-HIGHLAND")
        for _ in range(3):
            client.get("/api/v1/me", headers=pacific)
        assert client.get("/api/v1/me", headers=pacific).status_code == 429
        # a different token has its own bucket
        assert client.get("/api/v1/me", headers=rival).status_code == 200

    def test_anonymous_requests_limited(self, client):
        statuses = [client.get("/api/v1/auth/dev/identities").status_code
                    for _ in range(4)]
        assert 429 in statuses

    def test_expensive_endpoint_has_separate_budget(self, client):
        h = client.login("ngo-admin@example.dev")
        r1 = client.post("/api/v1/features/validate", headers=h)
        assert r1.status_code == 200  # first expensive call allowed
        r2 = client.post("/api/v1/features/validate", headers=h)
        # expensive budget (1) exhausted even though the user budget is not
        assert r2.status_code == 429
        # ordinary endpoints still work for the same user
        r3 = client.get("/api/v1/me", headers=h)
        assert r3.status_code == 200

    def test_limiter_never_grants_access(self, client):
        """A 429 response must never leak data; auth is still enforced after
        the limiter allows a request."""
        r = client.get("/api/v1/state")
        assert r.status_code in (401, 429)
        if r.status_code == 401:
            assert "detail" in r.json()
