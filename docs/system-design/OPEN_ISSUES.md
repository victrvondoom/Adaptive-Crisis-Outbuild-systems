# Open Issues — Phase V

## P1

1. Edge/CDN rate limiting + managed LB/proxy verification: BLOCKED — requires
   a deployed cloud environment.
2. Real LLM provider path (breaker + backoff are wired but unexercised
   against a live endpoint): BLOCKED — no API keys.
3. OutSystems ODC: BLOCKED — no access; Studio labels it honestly.
4. Scheduler production trigger: today `POST /api/v1/scheduler/tick` (manual/
   CI-cron). A platform scheduler (EventBridge/cron) should call it — needs
   deployment authorization.
5. Studio lab coverage: 5 scenarios (3 REAL, 2 SIMULATED). The remaining 15
   curriculum scenarios map to already-tested behaviors but have no dedicated
   lab card.

## P2

6. Per-replica limiter budgets: a multi-replica deployment should share
   buckets (Redis) or delegate to the edge — prepared, not needed at 1 replica.
7. Rate-limit observability: counts are in-memory; exporting rejected-request
   metrics needs a metrics backend (none installed by decision).
8. Studio light-theme scope is Studio-focused (the operational workspaces
   remain dark by design — operator preference).

## P0: none open. No P0 regressions (queue concordance, tenant isolation,
optimizer proofs all green in the 256-test suite).
