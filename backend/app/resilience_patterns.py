"""Phase V resilience patterns: token-bucket rate limiting, circuit breaker,
classified retries with full-jitter exponential backoff.

These are the deterministic, dependency-free implementations backing
System Design Studio topics 01, 10, 12, 13. They are wired into the real
request path (rate limiting middleware in main.py) and the LLM provider
path (breaker + retry in agents_runtime).
"""
import random
import threading
import time
from typing import Any, Callable, Optional


# ======================================================================
# Topic 01 — Token-bucket rate limiter (per-scope, thread-safe)
# ======================================================================

class TokenBucket:
    """Classic token bucket: capacity tokens, refill_rate tokens/second.
    Bucket is "burst + sustained rate" in one structure."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.updated: float | None = None

    def try_take(self, now: float, tokens: float = 1.0) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds)."""
        if self.updated is not None:
            self.tokens = min(self.capacity,
                              self.tokens + (now - self.updated) * self.refill_rate)
        self.updated = max(now, self.updated or now)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        retry_after = (tokens - self.tokens) / self.refill_rate
        return False, round(retry_after, 3)


class RateLimiter:
    """Scope-keyed buckets with independent budgets. Scopes are arbitrary
    strings ("ip:1.2.3.4", "user:<id>", "org:ORG-PACIFIC") so one abusive
    identity or tenant cannot consume another's quota."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def check(self, scopes: list[tuple[str, int, float]], now: float) -> tuple[bool, float, str]:
        """scopes: list of (scope_key, capacity, refill_rate). All scopes must
        allow. Returns (allowed, retry_after, limiting_scope)."""
        retry_after = 0.0
        limiting = ""
        allowed = True
        with self._lock:
            for key, capacity, refill in scopes:
                bucket = self._buckets.get(key)
                if bucket is None or bucket.capacity != capacity:
                    bucket = TokenBucket(capacity, refill)
                    self._buckets[key] = bucket
                ok, wait = bucket.try_take(now)
                if not ok:
                    allowed = False
                    if wait > retry_after:
                        retry_after, limiting = wait, key
        return allowed, retry_after, limiting

    def reset(self, prefix: str = ""):
        with self._lock:
            if not prefix:
                self._buckets.clear()
            else:
                for k in [k for k in self._buckets if k.startswith(prefix)]:
                    del self._buckets[k]


# ======================================================================
# Topics 12-13 — Classified retry with full-jitter exponential backoff
# ======================================================================

class RetryDeadlineExceeded(Exception):
    pass


def retry_with_backoff(fn: Callable[[], Any],
                       is_retryable: Callable[[BaseException], bool],
                       max_attempts: int = 3,
                       base_delay: float = 1.0,
                       max_delay: float = 30.0,
                       deadline: Optional[float] = None,
                       jitter: bool = True,
                       sleep: Callable[[float], None] = time.sleep,
                       now: Callable[[], float] = time.monotonic) -> Any:
    """Retries ONLY errors the caller classifies as transient (e.g. 5xx,
    timeouts). Never retries permanent client errors by construction: the
    classifier decides. Full jitter prevents synchronized retry storms.

    Honors an overall deadline: once exceeded, raises RetryDeadlineExceeded.
    """
    started = now()
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except BaseException as e:  # noqa: BLE001 — classified below
            if not is_retryable(e):
                raise
            if attempt >= max_attempts:
                raise
            if deadline is not None and (now() - started) + base_delay * (2 ** (attempt - 1)) > deadline:
                raise RetryDeadlineExceeded(
                    f"retry deadline exceeded after {attempt} attempt(s)") from e
            # Full jitter: uniform in [0, min(max_delay, base*2^(n-1))]
            ceiling = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = random.uniform(0, ceiling) if jitter else ceiling
            sleep(delay)


# ======================================================================
# Topic 10 — Circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
# ======================================================================

class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    """Fail-fast protection around a dependency. A breaker is NOT a timeout:
    the call itself must carry its own timeout. When OPEN, calls fail in
    microseconds instead of piling up threads, giving the dependency time
    to recover; HALF_OPEN admits limited probes to test recovery."""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max_calls: int = 1):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._lock = threading.Lock()
        self.state = "CLOSED"
        self.failure_count = 0
        self.opened_at: float = 0.0
        self.half_open_calls = 0

    def _transition(self, now: float):
        if self.state == "OPEN" and (now - self.opened_at) >= self.recovery_timeout:
            self.state = "HALF_OPEN"
            self.half_open_calls = 0

    def call(self, fn: Callable[[], Any],
             now: float = None) -> Any:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._transition(now)
            if self.state == "OPEN":
                raise CircuitOpenError(
                    f"circuit '{self.name}' is OPEN — failing fast")
            if self.state == "HALF_OPEN":
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        f"circuit '{self.name}' HALF_OPEN probe limit reached")
                self.half_open_calls += 1
        try:
            result = fn()
        except BaseException:
            with self._lock:
                if self.state == "HALF_OPEN":
                    # Probe failed: re-open for another recovery window
                    self.state = "OPEN"
                    self.opened_at = now
                    self.half_open_calls = 0
                else:
                    self.failure_count += 1
                    if self.failure_count >= self.failure_threshold:
                        self.state = "OPEN"
                        self.opened_at = now
            raise
        with self._lock:
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"  # probe succeeded
            self.failure_count = 0
        return result

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
