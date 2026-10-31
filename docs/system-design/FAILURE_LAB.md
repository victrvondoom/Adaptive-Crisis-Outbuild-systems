# Failure Lab (Phase V)

The System Design Studio "🧪 Failure Lab" runs scenarios live in the browser
against the real backend. REAL scenarios call actual endpoints and display the
actual responses; SIMULATED scenarios visualize behavior that is proven by
deterministic automated tests (with the test reference shown in the result).

| Scenario | Kind | Initial state | Injected failure | Expected | Actual (live) | Recovery | Evidence |
|---|---|---|---|---|---|---|---|
| 1 — Rate limit exceeded | REAL | authenticated session | hammer /api/v1/me past the user budget | 429 + Retry-After | shown live per run | wait Retry-After; bucket refills | test_rate_limiter.py |
| 14 — Duplicate delivery confirmation | REAL | dispatched mission in queue | confirm the same delivery twice | 2nd returns original receipt, `duplicate: true`, inventory deducted once | shown live per run | none needed (idempotent by design) | test_api.py, test_phase4_security.py |
| 15 — Poison message | SIMULATED | outbox event pending | worker crashes on processing (fault-injection hook in tests) | 4 retries then DEAD-LETTER with preserved error | deterministic test result | admin inspects/replays; main queue drains | test_resilience_patterns.py::TestOutboxDeadLetter |
| 10 — Circuit opens | SIMULATED | LLM provider healthy | 5 consecutive provider failures | OPEN → instant CircuitOpenError → HALF_OPEN probe → CLOSED | deterministic test result | breaker recovery window + probe | test_resilience_patterns.py |
| 20 — Duplicate scheduled job | REAL | scheduler idle | fire the tick twice back-to-back | 2nd tick: `skipped_not_due` — no double execution | shown live per run | none needed (atomic claim) | test_scheduler.py |

Rules enforced by the lab:

- Nothing is claimed to have run unless a durable row or live response says so.
- SIMULATED results always name the automated test that proves the behavior.
- The lab never mutates records outside the demo scenario, and never touches
  another tenant's data (permission-gated endpoints, org-scoped queries).
