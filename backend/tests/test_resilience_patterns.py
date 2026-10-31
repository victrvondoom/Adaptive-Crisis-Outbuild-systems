"""Phase V resilience-pattern tests (Studio topics 10, 12, 13, 15).

Circuit breaker state machine, classified retries, full-jitter backoff,
deadline enforcement, and outbox dead-lettering.
"""
import pytest

from app.resilience_patterns import (CircuitBreaker, CircuitOpenError,
                                     RetryDeadlineExceeded, retry_with_backoff)


class TestCircuitBreaker:
    def test_closed_when_healthy(self):
        cb = CircuitBreaker("t", failure_threshold=3, recovery_timeout=30)
        assert cb.call(lambda: "ok") == "ok"
        assert cb.state == "CLOSED"

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("t", failure_threshold=3, recovery_timeout=30)

        def boom():
            raise RuntimeError("down")
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(boom)
        assert cb.state == "CLOSED"
        with pytest.raises(RuntimeError):
            cb.call(boom)
        assert cb.state == "OPEN"

    def test_open_fails_fast_without_calling_dependency(self):
        cb = CircuitBreaker("t", failure_threshold=1, recovery_timeout=30)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        calls = []
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: calls.append(1))
        assert calls == []  # the dependency was never touched

    def test_half_open_probe_and_recovery(self):
        cb = CircuitBreaker("t", failure_threshold=1, recovery_timeout=0.0)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert cb.state == "OPEN"
        # recovery_timeout=0 -> immediately half-open; a successful probe closes
        assert cb.call(lambda: "recovered") == "recovered"
        assert cb.state == "CLOSED"

    def test_half_open_probe_limit(self):
        cb = CircuitBreaker("t", failure_threshold=1, recovery_timeout=10.0,
                            half_open_max_calls=1)
        probes = {"n": 0}

        def probe():
            probes["n"] += 1
            raise RuntimeError("still failing")
        with pytest.raises(RuntimeError):
            cb.call(probe, now=0.0)   # trips the breaker (OPEN at t=0)
        # inside the recovery window: fail fast, no probe admitted
        with pytest.raises(CircuitOpenError):
            cb.call(probe, now=5.0)
        assert probes["n"] == 1
        # after the window: exactly ONE probe is admitted
        with pytest.raises(RuntimeError):
            cb.call(probe, now=15.0)
        assert probes["n"] == 2
        # the failed probe re-opened the breaker -> fail fast again
        with pytest.raises(CircuitOpenError):
            cb.call(probe, now=15.0)
        assert probes["n"] == 2

    def test_failed_probe_reopens(self):
        cb = CircuitBreaker("t", failure_threshold=1, recovery_timeout=0.0)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still down")))
        assert cb.state == "OPEN"


class TestRetryBackoff:
    def test_retries_only_transient_errors(self):
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("transient")
            return "ok"
        sleeps = []
        result = retry_with_backoff(
            flaky, is_retryable=lambda e: "transient" in str(e),
            base_delay=0.01, sleep=sleeps.append, now=lambda: 0.0)
        assert result == "ok" and attempts["n"] == 3
        assert len(sleeps) == 2

    def test_permanent_error_not_retried(self):
        attempts = {"n": 0}

        def bad_request():
            attempts["n"] += 1
            raise ValueError("400 Bad Request")
        with pytest.raises(ValueError):
            retry_with_backoff(
                bad_request, is_retryable=lambda e: False,
                base_delay=0.01, sleep=lambda s: None)
        assert attempts["n"] == 1

    def test_max_attempts_bounded(self):
        attempts = {"n": 0}

        def always_503():
            attempts["n"] += 1
            raise RuntimeError("503")
        with pytest.raises(RuntimeError):
            retry_with_backoff(
                always_503, is_retryable=lambda e: True, max_attempts=3,
                base_delay=0.01, sleep=lambda s: None)
        assert attempts["n"] == 3

    def test_jitter_bounds(self):
        delays = []
        # full jitter: delay ~ U(0, min(max, base*2^n)); never negative, never over cap
        for n in range(200):
            captured = []

            def boom():
                raise RuntimeError("t")
            try:
                retry_with_backoff(
                    boom, is_retryable=lambda e: True, max_attempts=3,
                    base_delay=1.0, max_delay=2.0,
                    sleep=captured.append, now=lambda: 0.0)
            except RuntimeError:
                pass
            delays.append(captured[0])
        assert all(0.0 <= d <= 2.0 for d in delays)
        assert max(delays) > 0.1  # not degenerate zero-delay

    def test_deadline_enforced(self):
        attempts = {"n": 0}

        def slow_transient():
            attempts["n"] += 1
            raise RuntimeError("timeout")
        with pytest.raises(RetryDeadlineExceeded):
            retry_with_backoff(
                slow_transient, is_retryable=lambda e: True, max_attempts=10,
                base_delay=5.0, deadline=1.0,
                sleep=lambda s: None, now=lambda: 0.0)
        assert attempts["n"] == 1  # no second attempt once deadline exhausted

    def test_success_first_try_no_sleep(self):
        sleeps = []
        assert retry_with_backoff(
            lambda: "fine", is_retryable=lambda e: True,
            sleep=sleeps.append) == "fine"
        assert sleeps == []


class TestOutboxDeadLetter:
    def test_failing_event_retries_then_dead_letters(self, client):
        """A poison event fails, is retried on later dispatches, and is
        dead-lettered after MAX_ATTEMPTS without losing its record."""
        from app import persistence_phase4
        h = client.login("coordinator@example.dev")
        intake = client.post("/api/v1/requests", headers=h, json={
            "requester_name": "DLQ Probe Shelter", "lat": 14.6, "lng": 120.98,
            "items": [{"item_type": "hygiene_kits", "quantity": 1, "unit": "kits"}],
            "priority": "LOW", "consent": {"granted": True}}).json()
        rid = intake["request"]["id"]
        key = f"request:ORG-PACIFIC:{rid}:created"
        # inject a fault ONLY for this event type, then dispatch repeatedly
        from app.db import session_scope
        from app import persistence
        from app.models_db import OutboxEventRow
        from sqlalchemy import select
        with session_scope() as s:
            row = s.execute(select(OutboxEventRow).where(
                OutboxEventRow.idempotency_key == key)).scalar_one()
            assert row is not None and row.processed_at is None
            outbox_id, attempts0 = row.id, row.attempts
        for _ in range(persistence_phase4.OUTBOX_MAX_ATTEMPTS):
            res = persistence_phase4.dispatch_outbox(
                fault_injector=lambda et: (_ for _ in ()).throw(
                    RuntimeError("worker crashed")) if et == "AidRequestCreated" else None)
        # after MAX_ATTEMPTS the event is dead-lettered (no longer pending)
        with session_scope() as s:
            row = s.get(OutboxEventRow, outbox_id)
            assert row.processed_at is not None
            assert "dead-lettered" in row.last_error
            assert row.attempts >= attempts0 + persistence_phase4.OUTBOX_MAX_ATTEMPTS
        # the main queue is drained for new events afterwards
        res = persistence_phase4.dispatch_outbox()
        assert all(e["event_type"] != "AidRequestCreated"
                   for e in res.get("dead_lettered", []))
