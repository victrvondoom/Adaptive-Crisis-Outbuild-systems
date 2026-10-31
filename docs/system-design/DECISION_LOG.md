# Decision Log — Phase V

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| V1 | App-level token-bucket limiter, not edge-only | Real P1 gap (OPEN_ISSUES from Phase IV); edge limiter is impossible without cloud creds but app-level metering protects shared CPU today | doing nothing until deployment |
| V2 | Token hash as user bucket key (not decoded claims) | cheap, no extra DB/decode on the hot path; authn still verified separately — the limiter never grants access | per-request JWT decode (latency + duplication of auth layer) |
| V3 | Circuit breaker on the LLM provider path with NO silent deterministic fallback | anti-fabrication: silently swapping the deterministic handler in would fake model output; honest semantics = ProviderError → execution FAILED | auto-fallback (fabrication risk) |
| V4 | Full-jitter backoff + honor Retry-After | prevents synchronized retry storms; the 429 response carries Retry-After so clients mirror it | linear sleep (old code — replaced) |
| V5 | Outbox DLQ as dead-letter-by-attempt (5) with preserved error | bounded redelivery, inspectable/replayable; no new infra | unbounded retries (poison clogs queue) |
| V6 | DB-claimed durable scheduler; interval-based, UTC | duplicate/concurrent ticks are no-ops even multi-replica; DST-proof; honest last-run state | per-process crontab (duplicate execution across replicas) |
| V7 | Studio as a separate JS module + data file | keeps app.js stable; content data editable without touching logic | giant single-file splice (fragile) |
| V8 | REAL vs SIMULATED labels in the failure lab | anti-fabrication: live runs show live responses; simulations name their proving tests | presenting all scenarios as live |
| V9 | Explicit NOT REQUIRED for K8s/Kafka/Redis/2PC/event-sourcing | the Golden Rule: simplest architecture meeting requirements | installing curriculum technologies as cargo cult |
| V10 | Fixed a real bug found by testing: exempt-path tuple matched every path (`"/"` prefix) | caught by the failing limiter tests; the limiter was exempting everything | weakening the tests (rejected) |
