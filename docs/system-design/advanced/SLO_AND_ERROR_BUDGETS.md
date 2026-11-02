# SLIs, SLOs and Error Budgets (Topic 37)

Definitions: SLI measured; SLO target; SLA external contract (none exists); error budget = (1−SLO)×events.
Candidate indicators:
| SLI | Source | Numerator / Denominator | Window | Exclusions | Candidate threshold | Owner | Alert | Status |
|---|---|---|---|---|---|---|---|---|
| API availability | telemetry request buffer | status<500 / eligible /api/v1 requests | since process start (must become 28–30 d with durable metrics) | health, labs, benchmark, sim, 401/403/429 not "bad" | 99% (candidate) | NGO platform owner (TBD) | burn >100% budget | **MEASURED live** (needs ≥20 requests) |
| Successful request creation | audit/outbox | created / attempted | 30 d | validation 4xx | TBD | TBD | TBD | NOT_MEASURED |
| Delivery-confirmation persistence | receipts vs confirm calls | persisted / acknowledged | 30 d | duplicates | 100% of acknowledged | TBD | any miss = incident | NOT_MEASURED (no counter) |
| Optimizer availability | span status | OK / total `optimizer.solve_allocation` | 30 d | benchmarks | TBD | TBD | TBD | span data exists; window short |
| Agent action completion | agent_executions | SUCCEEDED+REVIEW / total | 30 d | injected failures | TBD | TBD | TBD | derivable from DB; not wired |
| Mission-state correctness | concordance metric | queue==plan | continuous | — | 1.0 | TBD | any <1 = P0 | tested, not exported |
| Data durability | restore drill | drills passing | quarterly | — | 100% | TBD | failed drill | drill exists |
No target was derived from user research; none is an SLA. Simulated benchmark runs are never counted. Arithmetic is unit-tested (990/1000 at 99% ⇒ 100% consumed).
