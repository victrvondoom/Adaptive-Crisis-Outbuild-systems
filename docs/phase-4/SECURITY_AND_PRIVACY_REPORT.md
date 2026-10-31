# Security and Privacy Report (Phase IV, Wave 11)

## Method

Reproducible adversarial tests in `backend/tests/test_phase4_security.py`
(11 tests, all passing) plus the existing Phase II security suites
(`test_authz_phase2.py`, tenant-isolation cases across all mission tests).
All testing used synthetic identities and temporary databases; no real
beneficiary data exists in this system.

## Confirmed protections (tested, reproducible)

| Probe | Result | Test |
|---|---|---|
| Cross-tenant transfer action (wrong org) | 403 fail-closed | test_cross_tenant_transfer_actions_fail_closed |
| Forged `X-Org-Id` header with foreign token | 401/403 (membership scope checked) | same |
| Transfer id enumeration | 404 without existence leak | test_transfer_id_enumeration |
| Cross-tenant procurement read + act | isolation holds; actions fail closed | test_procurement_cross_tenant_read_isolation |
| Stored XSS via intake fields | tags/control chars stripped at intake; trace clean | test_xss_payloads_never_stored_raw |
| Prompt injection in raw_text | canonical detector flags + strips; never obeyed | test_prompt_injection_is_flagged_not_obeyed |
| Consent double-revoke replay | second revoke 404; exactly one audit row; chain valid | test_consent_replay_and_double_revoke |
| Procurement receipt replay | 409; exactly one ledger movement | test_procurement_receipt_replay_cannot_double_stock |
| Transfer dispatch replay | 409; exactly one out-movement | test_transfer_dispatch_replay_cannot_double_move |
| Audit chain integrity after Phase IV event types | chain verifies | test_audit_chain_tamper_detection_still_strong |
| Permission matrix on new endpoints (transfers, budgets, suppliers) | 403 for volunteer/auditor | test_budget_and_transfer_permission_matrix |
| Coordinate/quantity boundary abuse | 422 | test_intake_rejects_hostile_field_values |
| SQL-injection-shaped strings | stored as inert data via parameterized ORM | same |

## Privacy posture

- Beneficiary consent: REQUIRED at API intake, revocable, and enforced at
  delivery confirmation (409 while revoked). Seeded demo requests carry no
  consent row and no consent claim is made for them (documented, not asserted).
- Data minimization: intake collects requester name, location, items, people
  count — no identity documents, no sensitive traits, no automated eligibility
  decisions.
- Cross-NGO privacy: only transfer facts (item, quantity, status, org ids)
  cross the boundary; each org's audit trail records only its own actions.

## Theoretical risks NOT confirmed as vulnerabilities (honest register)

- JWT algorithm confusion / issuer tampering: token issuance is dev-only
  (`DevAdapter` gated by env); production adapter requires real OIDC —
  **BLOCKED**, so production token hardening cannot be verified here.
- CSRF: the SPA uses bearer headers (no cookies), so classic CSRF does not
  apply; no cookie-based session exists to protect.
- SSRF / unsafe file upload / webhook replay: no file upload, outbound fetch,
  or webhook receiver exists in the product — not attackable surfaces today.
- Rate limiting / API abuse detection: NOT IMPLEMENTED (PROPOSED, atlas
  SEC domain) — a real production deployment gap, listed in OPEN_ISSUES.md.

No secret values exist in the repository (verified by history: env-gated config
only).
