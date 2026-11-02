# ADV-ADR-039 — Multi-region & Data Residency

Status: **NOT REQUIRED now**. Evaluation: users/NGOs unspecified geographically; no residency authorisation exists; one deployment; latency of a single-region API is not a measured problem; availability target not set; cost/complexity roughly 2×. Decision: single region. Do not replicate beneficiary data across regions without a documented, authorised residency decision.
Simulation (labelled): restricted tenants cannot replicate abroad; if their home region fails they are UNAVAILABLE; unrestricted tenants may fail over (async lag ⇒ possible loss). Not tested: real regional failure, replica lag, failover readiness (no infrastructure). Revisit when: a named NGO requires a region, or an SLO needs regional survivability.
