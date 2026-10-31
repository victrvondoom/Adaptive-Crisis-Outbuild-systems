# System Design Documentation — AIDNEXUS ONE (Phase V)

The System Design Studio (frontend "🏗️ System Design" tab) is the interactive
companion to these documents. Every status label is honest: a topic is
IMPLEMENTED only when code + tests exist in this repository.

| Document | Content |
|---|---|
| [DECISION_MATRIX.md](DECISION_MATRIX.md) | All 20 topics: IMPLEMENT / PREPARE / MANAGED / NOT REQUIRED / BLOCKED with rationale + evidence |
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | The actual topology and the golden rule applied |
| [IMPLEMENTATION_MATRIX.md](IMPLEMENTATION_MATRIX.md) | Topic → module → test mapping |
| [TEST_MATRIX.md](TEST_MATRIX.md) | Failure-condition coverage per pattern |
| [FAILURE_LAB.md](FAILURE_LAB.md) | Studio failure scenarios, REAL vs SIMULATED |
| [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md) | Authoritative sources and verification status |
| [EXECUTION_STATE.md](EXECUTION_STATE.md) / [WORKLOG.md](WORKLOG.md) / [DECISION_LOG.md](DECISION_LOG.md) / [OPEN_ISSUES.md](OPEN_ISSUES.md) / [TEST_EVIDENCE.md](TEST_EVIDENCE.md) | Session evidence |

## Quick facts

- Suite: **256 backend tests + 11 browser journeys, all green** with rate
  limiting ACTIVE in every request path.
- New Phase V code: `app/resilience_patterns.py` (token bucket, circuit
  breaker, retry/backoff), `app/scheduler.py` (+ migration v4), rate-limit
  middleware in `main.py`, outbox dead-lettering, breaker+backoff wiring in
  the LLM provider path.
- Explicitly rejected: Kubernetes, Kafka/RabbitMQ/Redis, Nginx-in-repo,
  2PC, event sourcing (see DECISION_MATRIX class-D entries).
