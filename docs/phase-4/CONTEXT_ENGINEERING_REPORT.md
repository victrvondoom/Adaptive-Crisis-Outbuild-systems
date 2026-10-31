# Context Engineering Report (Phase IV, Wave 8)

## Objective

Correct information at the correct time — not more text. The context
subsystem exists and is exercised; this report documents actuals.

## A. Context construction — IMPLEMENTED + TESTED

`ContextEnvelope` (`agents_runtime.py`) is built per action with: organization
id, actor id + role, mission id, active plan version, optimization run id,
policy version, data snapshot timestamp, evidence references, permitted
actions, and the current operational state digest. Construction happens after
tenant authorization (`guard()`), so a context envelope can never be built for
an org the actor does not belong to.

## B. Context quality — IMPLEMENTED (freshness) / PROPOSED (richer evals)

- **Freshness**: `check_freshness(now, active_plan_version, policy_version)`
  marks contexts stale with explicit reasons; stale contexts are rejected.
- **Permission correctness**: permitted_actions are declared per action and
  the endpoint enforces the permission matrix.
- **Contradiction detection / relevance ranking / completeness scoring**:
  PROPOSED (atlas CTX domain) — no fabricated quality claims.

## C. Context memory — PARTIAL

Mission history, plan decisions and recovery history are durable
(`plan_versions`, `disruptions`, `audit_events`) and available to context
builders. Organization-specific policy memory beyond `POLICY_VERSION`:
PROPOSED. No sensitive personal data is stored in generalized memory —
beneficiary data lives only in org-scoped request rows with consent records.

## D. Context invalidation — IMPLEMENTED (by construction)

Envelopes are built per action at execution time and never cached across
mutations, so inventory changes, plan changes, permission revocations,
request changes, disruptions and policy changes are always reflected.
`check_freshness` guards the boundary for any future caching.

## E. Context evaluation — TESTED (core) / PROPOSED (datasets)

Tested: tenant isolation (no cross-org context), stale-context rejection,
permission filtering. Reproducible context-evaluation datasets for retrieval
relevance and contradiction handling: PROPOSED.

## Anti-fabrication statement

No claim of model-grounded context quality is made: the current provider is
the deterministic one; real LLM context quality evaluation is BLOCKED without
provider credentials.
