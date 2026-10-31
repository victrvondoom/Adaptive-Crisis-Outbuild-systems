# Phase IV Open Issues

## P1 (should fix before real production use)

1. **Production OIDC identity**: dev identities are env-gated; real IdP
   integration BLOCKED (needs issuer/client credentials). Token hardening
   (algorithm pinning, audience checks) can only be verified with a real IdP.
2. **Rate limiting / API abuse detection**: NOT IMPLEMENTED on any endpoint.
3. **Transfer approval buttons in the UI**: the dual-approval flow is complete
   at the API level with tests; in-UI approval controls are not built (deliberate
   restraint, see PRODUCT_TASTE_REVIEW.md).
4. **Live PostgreSQL verification**: code path exists; unverified against a
   real server (BLOCKED: credentials).
5. **OutSystems ODC native app**: BLOCKED (no authenticated access in this
   environment). REST contracts + blueprints prepared.
6. **Real LLM inference**: adapter implemented; BLOCKED (no provider keys).
   Agent budget/timeout/cost controls are required the moment real keys exist.
7. **Notification provider**: no credentials; system never claims messages sent.

## P2 (product depth)

8. Transfer transport feasibility (vehicle/route binding for transfers).
9. Cross-org joint impact report (each org currently reports its own side).
10. Context evaluation datasets (retrieval relevance, contradiction handling).
11. Optimality-gap measurement for the heuristic.
12. Dead-letter queue for repeatedly failing outbox events (currently every
    claim processes or marks with error; a retry-limit → DLQ path is specified
    in the outbox schema but not yet exercised).

## P0: none open.
