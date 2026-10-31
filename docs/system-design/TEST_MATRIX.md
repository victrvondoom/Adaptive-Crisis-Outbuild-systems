# Test Matrix (Phase V)

Failure-condition coverage per implemented pattern. All tests deterministic;
run: `cd backend && python -m pytest` (256 passed at Phase V close).

| Pattern | Failure conditions tested | Test file |
|---|---|---|
| Rate limiting | burst exhaustion, 429 + Retry-After contract, per-tenant isolation, anonymous vs authenticated budgets, expensive-endpoint quota, exempt endpoints, limiter never grants access | tests/test_rate_limiter.py |
| Circuit breaker | threshold trip, OPEN fail-fast (dependency never touched), recovery window, HALF_OPEN single probe, failed probe re-opens, healthy close | tests/test_resilience_patterns.py |
| Retries | transient-only classification, permanent never retried, max attempts, deadline exhaustion | tests/test_resilience_patterns.py |
| Backoff | full-jitter bounds [0, cap] over 200 samples, no sleep on success | tests/test_resilience_patterns.py |
| Idempotency | replayed delivery (original receipt returned), concurrent duplicate constraints, conflicting key+payload, transfer/procurement replay (single ledger row) | test_api.py, test_phase4_security.py, test_mission_c/d |
| Outbox + DLQ | duplicate dispatch no-op, poison message retries then dead-letters with preserved error, permission gating | test_resilience_patterns.py, test_mission_events.py |
| Saga (transfers) | ownership/stock validation, sequential dual approval, wrong-org 403, cancellation, dispatch-time shortfall FAILED, replay | test_mission_c_e2e.py |
| Scheduler | duplicate trigger no-op, locked job skipped, failure recorded + retried, UTC storage, endpoint permissions | tests/test_scheduler.py |
| Single-DB transactions | both ledger movements commit or neither; concurrent allocation never exceeds stock | test_mission_c_e2e.py, test_persistence_phase2.py |
| Security (cross-cutting) | tenant boundary bypass, forged org headers, XSS, prompt injection, SQLi-shaped data inert, replay attacks | test_phase4_security.py, test_authz_phase2.py |
| Browser (Studio) | 20 topics render, detail fields, quiz reveal, map inspection, trace steps, REAL scheduler lab, theme toggle | tests/browser/test_journeys.py (11 journeys) |

## Honest gaps

- Load-balancer failover, proxy spoofing, TLS: MANAGED BY PLATFORM — cannot be
  integration-tested without a deployed environment (BLOCKED).
- LLM breaker against a real provider: tested via the pattern suite; the live
  endpoint itself is BLOCKED (no keys).
- Multi-replica scheduler contention: lock logic is DB-atomic and unit-tested;
  a true multi-replica deployment test requires infra not present here.
