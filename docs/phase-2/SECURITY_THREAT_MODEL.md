# PHASE II SECURITY THREAT MODEL & RED TEAM RESULTS

Scope: the Phase II multi-tenant, authenticated service. No security
certification is claimed — these are implemented controls + executed tests.

## Threat model (STRIDE summary)

| Threat | Vector | Control | Verification |
|---|---|---|---|
| Spoofing | forged/invalid/expired token; wrong issuer/audience | JWT signature+iss+aud+exp; session liveness | `test_authz_phase2` cases 7-10 + OIDC suite |
| Tampering | modified audit payloads | hash chain (prev-hash + recomputation) | `test_persistence_phase2::TestAuditChain` (tamper detected) |
| Repudiation | unlogged consequential actions | every action writes chained event | `test_audit_coverage_of_key_events` |
| Info disclosure | cross-tenant reads/writes; PII in logs | membership-derived scopes; synthetic demo data; logs contain ids only | 10-case isolation suite; browser UI denial test |
| DoS | oversized payloads; concurrency abuse | field length caps; 422/400; DB constraints bound repeated work | `test_disruption_payload_hardened`, concurrency tests |
| Elevation | volunteer approving; auditor writing; client-chosen org id | permission matrix, fail-closed scope resolution | `TestRoleMatrix` + API 403 tests |

## Red-team test results (all executed)

- Cross-tenant read/plan/delivery/inventory: **403** (API) and UI denial toast (browser test)
- Volunteer → approval: **403**; Auditor → write: **403**; unknown role: fail-closed
- Revoked session replay: **401** (logout revokes jti; `test_7_revoked_session_invalidated`)
- Invalid issuer / audience / expired / garbage tokens: **401**
- Missing identity: **401** (fail closed, 3 header variants)
- Stored-XSS regression: escaping verified in render paths; payload hardening strips control chars + caps lengths (422)
- SQL injection: SQLAlchemy bound parameters everywhere; no raw string SQL with user input
- Prompt injection in beneficiary text: sanitized + flagged (`test_prompt_injection_sanitized`)
- DB-level integrity: UNIQUE idempotency keys (movements, receipts, outbox, audit) + CHECK quantity≥0 — replay/negative-stock attempts raise IntegrityError (tested)
- Secrets: none in repo; env presence checked without printing values; CI secret scan gate

## Residual risks (documented, not hidden)

1. No rate limiting middleware yet (R4) — reverse proxy required before exposure.
2. SQLite local dev is not a concurrency-hardened production DB — Postgres path implemented, connection BLOCKED by credentials.
3. Audit retention is capped (5000 in-memory mirror; DB unbounded) — external append-only store recommended for production.
4. Demo identities are synthetic; real-user onboarding requires the OIDC path.
