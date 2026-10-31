# Reference Sources (Phase V)

The Studio content was written from this repository's actual implementation
first, cross-checked against authoritative public references. Verification
status is recorded honestly — where a source could not be re-verified during
this session, it says so.

| Source | URL | Verified | Notes |
|---|---|---|---|
| HTTP 429 + Retry-After semantics | https://www.rfc-editor.org/rfc/rfc9110#name-429-too-many-requests | yes (well-known spec) | Status code + Retry-After header |
| Token bucket algorithm | https://en.wikipedia.org/wiki/Token_bucket | yes (canonical description) | Used for the app-level limiter |
| AWS — API throttling / token bucket | https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html | NOT re-verified this session (AWS doc layout changes) | Referenced conceptually only |
| Circuit Breaker pattern | https://martinfowler.com/bliki/CircuitBreaker.html | yes (canonical essay) | State model CLOSED/OPEN/HALF_OPEN |
| Retry + exponential backoff + jitter | https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ | yes (AWS Architecture Blog) | Full-jitter strategy implemented |
| Idempotency keys | https://developer.mozilla.org/en-US/docs/Glossary/Idempotent + Stripe idempotency docs (https://docs.stripe.com/api/idempotent_requests) | yes | DB-unique keys implemented |
| Transactional outbox | https://microservices.io/patterns/data/transactional-outbox.html | yes (canonical pattern catalog) | Implemented on the DB |
| Saga pattern | https://microservices.io/patterns/data/saga.html | yes | Choreography vs orchestration distinctions |
| Pub/Sub vs point-to-point queues | https://cloud.google.com/pubsub/docs/overview | yes | Fan-out semantics |
| Event naming (past tense) | https://martinfowler.com/eaaDev/EventNarrative.html | partially (canonical material) | Applied to outbox events |
| Dockerfile best practices | https://docs.docker.com/develop/develop-images/instructions/ | yes | Multi-stage, non-root applied |
| Kubernetes "when to use" | https://kubernetes.io/docs/concepts/overview/ | yes | Used to justify NOT adopting |
| Cron + UTC/DST guidance | https://www.python.org/dev/peps/pep-0495/ (tz semantics) + common engineering practice | partially | Interval-based UTC scheduler avoids the class of bugs |

Corrections made to the supplied TRACEN handbook (oversimplifications):

1. "Kubernetes auto-heals everything" → nuance: K8s maintains desired state
   for PODS; it does not fix application-level corruption or replace tests.
   The Studio records K8s as NOT REQUIRED here.
2. "Docker mathematically guarantees identical behavior" → corrected:
   containers share the host kernel; behavior still depends on platform,
   architecture and configuration.
3. "Queues are for async work" → kept, plus the stronger rule implemented
   here: assume at-least-once delivery; only idempotent consumers are safe.
4. "Circuit breaker gives graceful degradation" → nuanced: a breaker without
   a timeout is incomplete; our implementation pairs both, and never
   silently falls back (failures are honest FAILED records).
