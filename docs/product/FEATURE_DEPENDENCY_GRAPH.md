# Feature Dependency Graph

Feature-level dependencies are recorded per record (`dependencies`). Below is the domain-level foundation graph; a domain depends on the foundations listed.

```mermaid
graph LR
  TEN[Multi-tenant foundations ORG/IDN/SEC]
  TEN --> INTAKE[Intake and triage INT/TRI/TAX]
  INTAKE --> PLAN[Planning and priority MIS/PRI/OPT/GEO]
  PLAN --> SUPPLY[Supply network INV/VOL/FLE/PRO]
  SUPPLY --> EXEC[Execution and recovery DSP/REC/FLD]
  EXEC --> AGENTS[Agentic platform AGT/CTX/TOL/APR]
  AGENTS --> EVIDENCE[Evidence and accountability EVD/ANA/SIM]
  EVIDENCE --> OUTER[Partners, finance, comms, climate API/FIN/DON/COM/DOC/CLM/GRI]
  TEN --> CLOUD[Platform and SRE CLD/SRE/UXP]
  CLOUD -.gates all waves.- TEN
```

## Highest-leverage foundations (unlock the most downstream domains)

1. Multi-tenant foundations (Wave 1) — unlock every tenant-scoped domain.
2. Planning + optimizer core (Wave 3) — unlock supply, execution, recovery.
3. Evidence/audit core — unlock analytics, benchmarks, accountability.

## Circular dependency check

Domain-level graph is a DAG (verified by construction above); feature-level `dependencies` reference existing feature ids or wave foundations only — `scripts/validate_feature_atlas.py` enforces referential integrity.
