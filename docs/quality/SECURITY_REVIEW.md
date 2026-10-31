# SECURITY REVIEW — AIDNEXUS ONE (post-repair)

Scope: this local-demo codebase. The production design (ODC, RBAC, tenant
isolation) is specified in `docs/security-model.md` and `../../outsystems/*.md`
but NOT_IMPLEMENTED here.

## Findings fixed this pass

| ID | Severity | Finding | Fix | Verification |
|---|---|---|---|---|
| S1 | HIGH | Stored XSS: disruption titles, requester names, audit summaries rendered via raw `innerHTML` | `escapeHtml()` on every dynamic render path in app.js; API strips control chars and caps lengths | Manual render-path review; payload hardening tested (`test_disruption_payload_hardened`) |
| S2 | HIGH | Prompt-injection path: beneficiary text stored and echoed verbatim | `sanitize_text()` strips instruction/script/handler patterns; injection detection flags request for review | `test_prompt_injection_sanitized` |
| S3 | HIGH | Unvalidated state transitions (any→any, incl. DELIVERED without receipt/inventory handling) | `ALLOWED_TRANSITIONS` enforced; DELIVERED only via confirmation endpoint | `TestTransitions`, API 400 tests |
| S4 | MEDIUM | CORS `allow_origins=["*"]` + `allow_credentials=True` | restricted to same-origin dev hosts; credentials disabled | `main.py` middleware |
| S5 | MEDIUM | Input length unbounded on free-text endpoints | Pydantic `max_length` + control-char stripping (422/400 on abuse) | `test_disruption_payload_hardened` |

## Remaining, documented (accepted for a local demo — must be fixed before any deployment)

| ID | Severity | Item | Mitigation before production |
|---|---|---|---|
| R1 | HIGH | No authentication/authorization on any endpoint | Implement ODC-side auth per `docs/security-model.md`; API keys/JWT + role checks (COORDINATOR/VOLUNTEER/AUDITOR/ADMIN) |
| R2 | HIGH | No multi-tenancy / organization isolation | Add tenant_id scoping to every entity + query |
| R3 | MEDIUM | In-memory state, no persistence/backup | DB with transactions; this is documented, not hidden |
| R4 | MEDIUM | No rate limiting / cost controls | Reverse-proxy limits; relevant mainly once LLM calls exist |
| R5 | LOW | Audit log in-memory with retention cap (5000) | External append-only store; chain preserved |
| R6 | LOW | Simulation controls publicly mutable | Auth + role gate |

## Data handling

- No real beneficiary data is stored: the scenario is synthetic (seed=42).
- `.env.example` contains placeholders only; no secrets exist in the repo;
  no `.env` was read during this audit.
- Delivery "signatures" in the demo are demo gestures (drawn pad content is
  represented, not cryptographically verified) — the UI labels receipts as
  demo-session actions.
