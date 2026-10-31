# Architecture Overview (Phase V)

```
 Browser SPA (vanilla JS, 9 workspaces incl. System Design Studio)
        │  bearer token + X-Org-Id
        ▼
 ┌─ Application edge (FastAPI middleware chain) ─────────────┐
 │ 1. Token-bucket rate limiter  (429 + Retry-After)         │
 │ 2. Correlation-id logging (X-Request-ID)                  │
 │ 3. Identity verification (fail-closed) + org scope        │
 └───────────────────────────────────────────────────────────┘
        ▼
 FastAPI modular monolith — 40+ endpoints, guard() per endpoint
   ├─ state engine (authoritative in-memory + write-through)
   ├─ optimizer (priority-preserving 2-opt heuristic)
   ├─ agent runtime (ContextEnvelope → provider → postconditions)
   │    └─ LLM HTTP path wrapped in circuit breaker + jitter backoff
   ├─ scheduler (DB-claimed jobs: outbox recovery, integrity, expiry)
   └─ persistence → SQLite (dev) / PostgreSQL (prod path)
        ├─ transactional outbox (+ dead-letter at 5 attempts)
        └─ hash-chained audit per org
 External (BLOCKED, honestly): ODC, real LLM keys, notifications.
 Managed by platform (at deployment): TLS, LB, edge rate limiting.
```

## The golden rule, applied

No architecture is universally best. This repository implements the patterns
with demonstrated need (limiter, breaker, retries, idempotency, outbox+DLQ,
scheduler, single-DB transactions, state-machine saga), prepares interfaces
for scale (pub/sub contracts, cache-aside), delegates to the platform
(TLS, LB), and explicitly rejects the rest (Kubernetes, Kafka, 2PC, event
sourcing) with recorded rationale in DECISION_MATRIX.md.

## Trust boundaries

1. Client → edge: untrusted (rate-limit scopes are metering, never auth).
2. Edge → handlers: verified identity object only; client-supplied identity
   headers are never trusted (test_phase4_security.py).
3. Org boundary: every DB query is org-scoped; cross-org facts (transfers)
   share only the minimum contract fields.
4. Agent boundary: models propose; deterministic workflows + human approval
   commit; postconditions verify against real state.
5. Scheduler/outbox: events are facts with tenant ids — a consumer re-checks
   authorization before acting.
