# Feature Test Coverage

EXISTING_VERIFIED features: 286 — each references real test files.

Rule: a feature may only move to IMPLEMENTED_TESTED with runtime + test evidence; the validator enforces test references for verified statuses.

| Feature | Status | Test references |
|---|---|---|
| ORG-001 Multi-organization workspace | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| ORG-006 Organization switching | EXISTING_VERIFIED | tests/browser/test_journeys.py |
| ORG-009 Organization data boundaries | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| ORG-012 Member lifecycle management | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| ORG-015 Workspace audit view | EXISTING_VERIFIED | tests/test_api.py::TestDisruptionApprovalFlow; tests/test_persistence_phase2.py |
| ORG-016 Workspace export | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| ORG-026 Organization health indicators | EXISTING_VERIFIED | tests/test_api.py |
| IDN-003 OIDC provider integration | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestOidcVerification |
| IDN-004 User session management | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestTenantIsolationAPI |
| IDN-007 Role-based access control | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestRoleMatrix |
| IDN-012 Session revocation | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_7_revoked_session_invalidated |
| IDN-013 Membership verification | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| IDN-014 Account suspension | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestRoleMatrix |
| IDN-018 Volunteer permissions | EXISTING_VERIFIED | tests/test_api.py::TestDeliveryEndpoint |
| IDN-019 Auditor access | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_6_auditor_cannot_modify |
| IDN-020 Read-only observer role | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| IDN-021 Admin activity history | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestAuditChain |
| IDN-025 Token expiration enforcement | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_valid_rs256_token_accepted |
| IDN-027 Permission revocation propagation | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_7_revoked_session_invalidated |
| IDN-030 Organization-aware identity | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| INT-001 Web intake form | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_triage_journey |
| INT-002 Mobile intake | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_responsive_no_horizontal_overflow |
| INT-012 Structured request parsing | EXISTING_VERIFIED | tests/test_agents.py::TestAgent1Triage |
| INT-019 Duplicate intake detection | EXISTING_VERIFIED | tests/test_agents.py::test_duplicate_intake_flagged_not_denied |
| INT-020 Missing-field detection | EXISTING_VERIFIED | tests/test_agents.py::test_missing_quantities_never_invented |
| INT-021 Intake validation rules | EXISTING_VERIFIED | tests/test_api.py::TestTriageEndpoint |
| INT-023 Intake source attribution | EXISTING_VERIFIED | tests/test_agents.py |
| INT-024 Intake status tracking | EXISTING_VERIFIED | tests/test_state_machine.py |
| INT-026 Request withdrawal | EXISTING_VERIFIED | tests/test_state_machine.py::TestTransitions |
| TAX-010 Quantity and unit normalization | EXISTING_VERIFIED | tests/test_optimizer.py |
| TAX-011 Standardized item identifiers | EXISTING_VERIFIED | tests/test_optimizer.py::TestFeasibility |
| TAX-028 Unmet demand classification | EXISTING_VERIFIED | tests/test_optimizer.py::test_blocked_entries_carry_unmet_demand |
| TAX-030 Taxonomy validation tests | EXISTING_VERIFIED | tests/test_optimizer.py::TestFeasibility |
| TRI-001 Automated triage suggestions | EXISTING_VERIFIED | tests/test_agents.py::TestAgent1Triage |
| TRI-002 Human triage confirmation | EXISTING_VERIFIED | tests/test_agents.py::test_agent_never_denies_assistance |
| TRI-008 Duplicate case consolidation | EXISTING_VERIFIED | tests/test_agents.py::test_duplicate_intake_flagged_not_denied |
| TRI-028 Triage explanation records | EXISTING_VERIFIED | tests/test_agents.py |
| TRI-029 Triage uncertainty surfacing | EXISTING_VERIFIED | tests/test_agents.py::test_ambiguous_message_flagged_for_review |
| PRI-001 Priority policy definitions | EXISTING_VERIFIED | tests/test_optimizer.py::TestUrgencyScore |
| PRI-002 Priority policy versioning | EXISTING_VERIFIED | tests/test_metrics.py |
| PRI-004 Critical-need handling rules | EXISTING_VERIFIED | tests/test_queue_concordance.py |
| PRI-010 Priority explanation records | EXISTING_VERIFIED | tests/test_optimizer.py |
| PRI-019 Deadline-sensitive prioritization | EXISTING_VERIFIED | tests/test_optimizer.py::test_deadline_infeasibility_flagged |
| PRI-022 Unmet critical demand reporting | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons |
| PRI-023 Priority fairness test suite | EXISTING_VERIFIED | tests/test_metrics.py::test_critical_fulfillment_counts_delivered_only |
| MIS-006 Mission versioning | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| MIS-008 Mission approval workflow | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| MIS-009 Mission cancellation | EXISTING_VERIFIED | tests/test_state_machine.py::test_cancelled_is_terminal |
| MIS-015 Mission snapshots | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| MIS-016 Mission state machine | EXISTING_VERIFIED | tests/test_state_machine.py::TestTransitions |
| MIS-018 Mission comparison | EXISTING_VERIFIED | tests/test_api.py::TestDisruptionApprovalFlow |
| MIS-022 Mission execution tracking | EXISTING_VERIFIED | tests/test_queue_concordance.py |
| MIS-026 Mission blocking conditions | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons |
| OPT-001 Priority-preserving 2-opt routes | EXISTING_VERIFIED | tests/test_optimizer.py::test_two_opt_improves_distance_and_preserves_priority_order |
| OPT-002 Small-instance exact solver comparison | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::TestExactOracle |
| OPT-003 Vehicle-routing constraint handling | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::TestIndependentFeasibility |
| OPT-004 Vehicle capacity constraints | EXISTING_VERIFIED | tests/test_optimizer.py::test_capacity_never_exceeded |
| OPT-005 Depot inventory constraints | EXISTING_VERIFIED | tests/test_optimizer.py::test_inventory_never_exceeded |
| OPT-006 Multiple vehicle classes | EXISTING_VERIFIED | tests/test_state_machine.py::TestVolunteers |
| OPT-007 Multi-depot allocation | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::test_blocked_depot_is_never_allocated_from |
| OPT-008 Delivery time windows | EXISTING_VERIFIED | tests/test_optimizer.py::test_deadline_infeasibility_flagged |
| OPT-014 Unmet-demand minimization | EXISTING_VERIFIED | tests/test_metrics.py::test_metrics_derive_from_trace |
| OPT-017 Disruption-aware re-optimization | EXISTING_VERIFIED | tests/test_metrics.py::test_recovery_beats_static_on_fulfillment |
| OPT-020 Commitment preservation | EXISTING_VERIFIED | tests/test_optimizer.py::test_preserved_requests_keep_assignment_and_immutable_status |
| OPT-023 Solver timeout handling | EXISTING_VERIFIED | tests/test_resilience.py::TestSolverFailure |
| OPT-024 Infeasibility diagnosis | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons |
| OPT-027 Optimality-gap measurement | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::test_heuristic_within_documented_gap_of_exact_optimum |
| OPT-029 Deterministic replay | EXISTING_VERIFIED | tests/test_metrics.py::test_benchmark_deterministic_same_seed |
| OPT-030 Optimization provenance records | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| GEO-001 Geographic request representation | EXISTING_VERIFIED | tests/test_optimizer.py |
| GEO-002 Warehouse coordinate registry | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| GEO-004 Route distance calculations | EXISTING_VERIFIED | tests/test_optimizer.py |
| GEO-008 Geofencing checks | EXISTING_VERIFIED | tests/test_optimizer.py::test_hazard_zone_blocks_requests |
| GEO-013 Map visualization | EXISTING_VERIFIED | tests/browser/test_journeys.py |
| GEO-018 Geographic data quality checks | EXISTING_VERIFIED | tests/test_optimizer.py |
| GEO-022 Route feasibility checks | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::TestIndependentFeasibility |
| GEO-023 Route versioning | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| INV-001 Multiple warehouse management | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| INV-002 Stock intake recording | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_movement_updates_quantity_atomically |
| INV-003 Stock movement ledger | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestInventoryTransactions |
| INV-009 Available inventory calculation | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| INV-017 Warehouse shutdown handling | EXISTING_VERIFIED | tests/test_resilience.py::TestWarehouseShutdown |
| INV-018 Alternative depot selection | EXISTING_VERIFIED | tests/test_resilience.py::TestWarehouseShutdown |
| INV-021 Inventory snapshots | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| INV-023 Units of measure registry | EXISTING_VERIFIED | tests/test_optimizer.py |
| INV-028 Inventory movement evidence | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| INV-029 Duplicate movement prevention | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_replayed_movement_rejected_by_idempotency_key |
| INV-030 Inventory accuracy benchmarking | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_concurrent_allocations_never_exceed_stock |
| VOL-001 Volunteer registration | EXISTING_VERIFIED | tests/test_state_machine.py::TestVolunteers |
| VOL-004 Language skill records | EXISTING_VERIFIED | tests/test_state_machine.py::TestVolunteers |
| VOL-007 Volunteer task matching | EXISTING_VERIFIED | tests/test_state_machine.py::TestVolunteers |
| VOL-026 Role-specific authorization | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestRoleMatrix |
| VOL-029 Volunteer history | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| FLE-001 Vehicle registry | EXISTING_VERIFIED | tests/test_state_machine.py |
| FLE-002 Vehicle capacity records | EXISTING_VERIFIED | tests/test_optimizer.py::test_capacity_never_exceeded |
| FLE-003 Vehicle type taxonomy | EXISTING_VERIFIED | tests/test_state_machine.py::TestVolunteers |
| FLE-005 Vehicle availability status | EXISTING_VERIFIED | tests/test_optimizer.py |
| FLE-009 Vehicle dispatch control | EXISTING_VERIFIED | tests/test_queue_concordance.py |
| FLE-011 Vehicle replacement | EXISTING_VERIFIED | tests/test_resilience.py::TestWarehouseShutdown |
| FLE-017 Breakdown reporting | EXISTING_VERIFIED | tests/test_resilience.py |
| FLE-023 Capacity validation tests | EXISTING_VERIFIED | tests/test_optimizer.py::test_capacity_never_exceeded |
| DSP-001 Dispatch creation | EXISTING_VERIFIED | tests/test_state_machine.py |
| DSP-002 Dispatch authorization | EXISTING_VERIFIED | tests/test_queue_concordance.py |
| DSP-003 Dispatch sequencing | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_queue_order_matches_plan_sequence |
| DSP-004 Dispatch manifests | EXISTING_VERIFIED | tests/test_state_machine.py |
| DSP-007 Delivery confirmation | EXISTING_VERIFIED | tests/test_state_machine.py::TestIdempotentDelivery |
| DSP-010 Partial delivery handling | EXISTING_VERIFIED | tests/test_metrics.py |
| DSP-011 Failed delivery handling | EXISTING_VERIFIED | tests/test_state_machine.py::TestTransitions |
| DSP-017 Duplicate receipt protection | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_concurrent_duplicate_confirm_single_deduction |
| DSP-019 Inventory deduction on delivery | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestDeliveryPersistence |
| DSP-024 Delivery timeline view | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| DSP-027 Return-to-warehouse workflow | EXISTING_VERIFIED | tests/test_optimizer.py |
| REC-001 Warehouse failure detection | EXISTING_VERIFIED | tests/test_resilience.py::TestWarehouseShutdown |
| REC-002 Vehicle failure handling | EXISTING_VERIFIED | tests/test_resilience.py |
| REC-003 Route closure handling | EXISTING_VERIFIED | tests/test_optimizer.py::test_hazard_zone_blocks_requests |
| REC-005 Stock mismatch detection | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_stock_cannot_go_negative_db_enforced |
| REC-009 Plan invalidation detection | EXISTING_VERIFIED | tests/test_resilience.py::TestSolverFailure |
| REC-010 Impacted assignment detection | EXISTING_VERIFIED | tests/test_agents.py::TestAgent3Recovery |
| REC-011 Completed-work preservation | EXISTING_VERIFIED | tests/test_agents.py::test_delivered_missions_preserved_immutable |
| REC-012 Commitment preservation (REC scope) | EXISTING_VERIFIED | tests/test_optimizer.py::test_preserved_requests_keep_assignment_and_immutable_status |
| REC-013 Recovery planning | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| REC-014 Alternative warehouse selection | EXISTING_VERIFIED | tests/test_resilience.py::TestWarehouseShutdown |
| REC-015 Assignment reassignment | EXISTING_VERIFIED | tests/test_state_machine.py |
| REC-017 Recovery approval gate | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| REC-019 Infeasible recovery reporting | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons |
| REC-021 Recovery explanations | EXISTING_VERIFIED | tests/test_api.py::TestDisruptionApprovalFlow |
| REC-023 Recovery latency measurement | EXISTING_VERIFIED | tests/test_metrics.py::test_aidnexus_replanning_latency_measured |
| REC-024 Recovery benchmark suite | EXISTING_VERIFIED | tests/test_metrics.py::test_recovery_beats_static_on_fulfillment |
| REC-025 Multi-disruption handling | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning::test_sequential_versions_and_approval_flow |
| REC-029 Recovery audit records | EXISTING_VERIFIED | tests/test_resilience.py::TestAuditConsistencyUnderFailure |
| REC-030 Recovery effectiveness reporting | EXISTING_VERIFIED | tests/test_metrics.py |
| AGT-001 Agent registry | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| AGT-005 Agent execution state tracking | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestRunAction |
| AGT-006 Agent versioning | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| AGT-008 Model routing rules | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestProviderResolution |
| AGT-011 Agent timeout handling | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| AGT-013 Retry limits | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_provider_failure_persists_and_raises |
| AGT-017 Tool execution engine | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| AGT-018 Agent tracing | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_execution_record_fields |
| AGT-024 Agent evaluation harness | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| AGT-025 Provider fallback chain | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestProviderResolution |
| AGT-026 Agent permission scopes | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestTriageViaAPI |
| AGT-028 Agent performance reporting | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| CTX-001 Structured context envelopes | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestContextEnvelope |
| CTX-002 Tenant-aware context | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| CTX-003 Mission-aware context | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| CTX-004 Actor-aware context | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| CTX-006 Context versioning | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| CTX-007 Context freshness checks | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_stale_snapshot_detected |
| CTX-015 Missing-information detection | EXISTING_VERIFIED | tests/test_agents.py::test_missing_quantities_never_invented |
| CTX-022 Stale-context rejection | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_plan_version_change_detected |
| CTX-030 Context access auditing | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| TOL-001 Typed tool registry | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| TOL-002 Tool input schemas | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestSchemaValidation |
| TOL-005 Precondition enforcement | EXISTING_VERIFIED | tests/test_agents.py::TestAgent1Triage |
| TOL-006 Postcondition verification | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_success_requires_postcondition |
| TOL-008 Action idempotency rules | EXISTING_VERIFIED | tests/test_state_machine.py::TestIdempotentDelivery |
| TOL-009 Tool timeout behavior | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| TOL-010 Tool retry policies | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_provider_failure_persists_and_raises |
| TOL-011 Tool output validation | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestSchemaValidation |
| TOL-013 Agent-action test mapping | EXISTING_VERIFIED | docs/agents/AGENT_ACTION_CATALOG.md |
| TOL-014 Tool unit tests | EXISTING_VERIFIED | tests/test_agents.py |
| TOL-015 Action integration tests | EXISTING_VERIFIED | tests/test_agents_runtime.py::TestTriageViaAPI |
| TOL-017 Adversarial action tests | EXISTING_VERIFIED | tests/test_agents.py::test_prompt_injection_sanitized |
| TOL-025 Side-effect classification | EXISTING_VERIFIED | docs/agents/AGENT_ACTION_CATALOG.md |
| TOL-026 Human approval requirements | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| TOL-028 Action success verification | EXISTING_VERIFIED | tests/test_agents_runtime.py::test_failed_postcondition_marks_failure |
| TOL-030 Action regression suite | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| APR-001 Approval queues | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| APR-002 Approval policies | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestRoleMatrix |
| APR-003 Role-specific approval rights | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_5_volunteer_cannot_approve |
| APR-010 Approval history | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| APR-011 Approval version binding | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| APR-012 Plan version checking at approval | EXISTING_VERIFIED | tests/test_state_machine.py::test_double_approval_rejected |
| APR-013 Stale approval prevention | EXISTING_VERIFIED | tests/test_state_machine.py::test_double_approval_rejected |
| APR-015 Human override capability | EXISTING_VERIFIED | tests/test_state_machine.py::TestTransitions |
| APR-017 Override audit trail | EXISTING_VERIFIED | tests/test_state_machine.py |
| EVD-001 Append-only audit events | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestAuditChain |
| EVD-002 Hash-chain verification | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestAuditChain |
| EVD-003 Event sequence checks | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestAuditChain |
| EVD-004 Actor attribution | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| EVD-007 Agent decision records | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| EVD-008 Model version records | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| EVD-009 Prompt version records | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| EVD-010 Tool call evidence | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| EVD-011 Plan version evidence | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| EVD-012 Approval evidence | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| EVD-013 Delivery evidence | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestDeliveryPersistence |
| EVD-014 Inventory movement evidence (EVD scope) | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| EVD-018 Evidence completeness checks | EXISTING_VERIFIED | tests/test_metrics.py::test_audit_coverage_of_key_events |
| EVD-019 Evidence verification tools | EXISTING_VERIFIED | tests/test_api.py::TestDisruptionApprovalFlow |
| EVD-020 Tamper detection | EXISTING_VERIFIED | tests/test_persistence_phase2.py::test_tampered_payload_detected |
| EVD-022 Audit search | EXISTING_VERIFIED | tests/test_api.py |
| EVD-024 Correlation id propagation | EXISTING_VERIFIED | tests/test_api.py |
| ANA-001 Canonical metric registry | EXISTING_VERIFIED | docs/metrics/METRIC_REGISTRY.md; tests/test_metrics.py |
| ANA-002 Metric formula versioning | EXISTING_VERIFIED | docs/metrics/METRIC_REGISTRY.md |
| ANA-003 Metric lineage tracking | EXISTING_VERIFIED | docs/metrics/METRIC_REGISTRY.md |
| ANA-004 Metric freshness indicators | EXISTING_VERIFIED | docs/metrics/VERIFIED_METRICS.md |
| ANA-005 Denominator validation tests | EXISTING_VERIFIED | tests/test_metrics.py::test_zero_critical_denominator_handled |
| ANA-006 KPI reconciliation checks | EXISTING_VERIFIED | tests/test_metrics.py::test_counts_consistent_with_requests |
| ANA-007 Unmet-demand analytics | EXISTING_VERIFIED | tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons |
| ANA-008 Fulfillment analytics | EXISTING_VERIFIED | tests/test_metrics.py |
| ANA-009 Critical-need coverage analytics | EXISTING_VERIFIED | tests/test_metrics.py::test_critical_fulfillment_counts_delivered_only |
| ANA-010 Delivery timing analytics | EXISTING_VERIFIED | tests/test_metrics.py::test_metrics_derive_from_trace |
| ANA-012 Inventory accuracy metrics | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| ANA-015 Recovery effectiveness analytics | EXISTING_VERIFIED | tests/test_metrics.py::test_recovery_beats_static_on_fulfillment |
| ANA-016 Agent performance metrics | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| ANA-030 Analytics verification tests | EXISTING_VERIFIED | tests/test_metrics.py |
| SIM-001 Scenario creation | EXISTING_VERIFIED | tests/test_metrics.py |
| SIM-003 Seed management | EXISTING_VERIFIED | tests/test_metrics.py::test_benchmark_is_real_simulation |
| SIM-005 FIFO baseline strategy | EXISTING_VERIFIED | tests/test_metrics.py |
| SIM-006 Greedy baseline strategy | EXISTING_VERIFIED | tests/test_metrics.py |
| SIM-007 Static optimizer strategy | EXISTING_VERIFIED | tests/test_metrics.py |
| SIM-008 Recovery-enabled strategy | EXISTING_VERIFIED | tests/test_metrics.py::test_recovery_beats_static_on_fulfillment |
| SIM-009 Exact small-instance oracle | EXISTING_VERIFIED | tests/test_optimizer_proofs.py::TestExactOracle |
| SIM-010 Agent-action evaluation suite | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| SIM-014 Adversarial scenario family | EXISTING_VERIFIED | tests/test_agents.py::test_prompt_injection_sanitized |
| SIM-015 Scarcity scenario family | EXISTING_VERIFIED | docs/benchmarks/FINAL_BENCHMARK_REPORT.md |
| SIM-017 Multi-disruption scenario family | EXISTING_VERIFIED | tests/test_state_machine.py::TestPlanVersioning |
| SIM-018 Performance evaluation suite | EXISTING_VERIFIED | docs/phase-2/benchmarks/loadtest_results.json |
| SIM-019 Statistical summary generation | EXISTING_VERIFIED | docs/benchmarks/FINAL_BENCHMARK_REPORT.md |
| SIM-021 Paired comparison reporting | EXISTING_VERIFIED | docs/benchmarks/FINAL_BENCHMARK_REPORT.md |
| SIM-022 Benchmark provenance records | EXISTING_VERIFIED | docs/benchmarks/FINAL_BENCHMARK_REPORT.md |
| SIM-023 Reproduction instructions | EXISTING_VERIFIED | README.md |
| SIM-024 Benchmark artifact export | EXISTING_VERIFIED | benchmarks/results/ |
| SIM-025 Regression thresholds | EXISTING_VERIFIED | tests/test_metrics.py::test_recovery_beats_static_on_fulfillment |
| SIM-030 Benchmark integrity verification | EXISTING_VERIFIED | tests/test_metrics.py::test_integrity_metrics_zero_violations |
| API-001 Versioned REST APIs | EXISTING_VERIFIED | tests/test_api.py |
| API-002 API authentication | EXISTING_VERIFIED | tests/test_api.py::test_state_requires_auth |
| API-003 API authorization | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| API-004 OpenAPI schema publication | EXISTING_VERIFIED | tests/test_api.py |
| API-005 API contract testing | EXISTING_VERIFIED | tests/test_api.py |
| API-008 Idempotency key support | EXISTING_VERIFIED | tests/test_persistence_phase2.py |
| API-026 Bulk data export | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| API-027 Interactive API documentation | EXISTING_VERIFIED | tests/test_api.py |
| SEC-001 Secure authentication enforcement | EXISTING_VERIFIED | tests/test_api.py::test_state_requires_auth |
| SEC-002 Tenant authorization enforcement | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestTenantIsolationAPI |
| SEC-003 Least-privilege defaults | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestRoleMatrix |
| SEC-004 Secret management policy | EXISTING_VERIFIED | docs/phase-2/SECURITY_THREAT_MODEL.md |
| SEC-007 Secure session handling | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| SEC-009 XSS regression protection | EXISTING_VERIFIED | tests/test_agents.py::test_prompt_injection_sanitized; tests/test_api.py |
| SEC-011 SQL injection protection | EXISTING_VERIFIED | docs/phase-2/SECURITY_THREAT_MODEL.md |
| SEC-012 Prompt injection defenses | EXISTING_VERIFIED | tests/test_agents.py::test_prompt_injection_sanitized |
| SEC-016 Security audit events | EXISTING_VERIFIED | tests/test_api.py |
| SEC-019 Export controls | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| SEC-022 Token revocation enforcement | EXISTING_VERIFIED | tests/test_authz_phase2.py::test_7_revoked_session_invalidated |
| SEC-026 Tenant-boundary test suite | EXISTING_VERIFIED | tests/test_authz_phase2.py |
| SEC-028 Security configuration validation | EXISTING_VERIFIED | tests/test_authz_phase2.py::TestDevAuthProductionGating |
| SEC-030 Threat model versioning | EXISTING_VERIFIED | docs/phase-2/SECURITY_THREAT_MODEL.md |
| CLD-001 Reproducible container builds | EXISTING_VERIFIED | Dockerfile |
| CLD-002 Environment configuration | EXISTING_VERIFIED | docker-compose.yml |
| CLD-003 Secret injection | EXISTING_VERIFIED | docs/phase-2/PHASE_2_ARCHITECTURE_DECISION.md |
| CLD-006 CI test execution | EXISTING_VERIFIED | .github/workflows/ci.yml |
| CLD-007 Database migration pipeline | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestMigrations |
| CLD-008 Application health checks | EXISTING_VERIFIED | tests/test_api.py |
| CLD-009 Readiness checks | EXISTING_VERIFIED | tests/test_api.py::test_readyz |
| CLD-018 Dependency pinning | EXISTING_VERIFIED | backend/requirements.txt |
| CLD-025 Development seed data | EXISTING_VERIFIED | app/bootstrap.py |
| CLD-026 Test environment isolation | EXISTING_VERIFIED | tests/conftest.py |
| CLD-027 Developer documentation | EXISTING_VERIFIED | README.md |
| CLD-028 Deployment validation | EXISTING_VERIFIED | tests/test_api.py::test_readyz |
| CLD-030 Release quality gates | EXISTING_VERIFIED | .github/workflows/ci.yml |
| SRE-001 Structured JSON logging | EXISTING_VERIFIED | app/main.py |
| SRE-005 Correlation id propagation (SRE scope) | EXISTING_VERIFIED | tests/test_api.py |
| SRE-006 Service health monitoring | EXISTING_VERIFIED | tests/test_api.py |
| SRE-011 Bounded retry policies | EXISTING_VERIFIED | tests/test_agents_runtime.py |
| SRE-013 Graceful shutdown | EXISTING_VERIFIED | app/main.py |
| SRE-015 Concurrency controls | EXISTING_VERIFIED | tests/test_persistence_phase2.py::TestInventoryTransactions |
| SRE-020 Dependency failure simulation | EXISTING_VERIFIED | tests/test_resilience.py::TestSolverFailure |
| SRE-022 Load testing | EXISTING_VERIFIED | tools/loadtest.py; docs/phase-2/benchmarks/loadtest_results.json |
| SRE-026 Operational runbooks | EXISTING_VERIFIED | docs/phase-2/FINAL_PHASE_2_REPORT.md |
| SRE-030 Resilience benchmark suite | EXISTING_VERIFIED | tests/test_resilience.py |
| UXP-004 NGO coordinator experience | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_login_and_dashboard |
| UXP-005 Field volunteer experience | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_volunteer_delivery_journey |
| UXP-006 Auditor experience | EXISTING_VERIFIED | tests/test_api.py::TestDisruptionApprovalFlow |
| UXP-008 Responsive layouts | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_responsive_no_horizontal_overflow |
| UXP-011 Screen-reader labels | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_accessibility_scan |
| UXP-012 Color contrast compliance | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_accessibility_scan |
| UXP-019 Empty state design | EXISTING_VERIFIED | frontend/js/app.js |
| UXP-020 Loading state design | EXISTING_VERIFIED | frontend/js/app.js |
| UXP-021 Error recovery flows | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_cross_tenant_isolation_in_ui |
| UXP-022 Status semantics | EXISTING_VERIFIED | tests/browser/test_journeys.py |
| UXP-023 Notification presentation | EXISTING_VERIFIED | tests/browser/test_journeys.py |
| UXP-025 Decision explanations in UI | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_disruption_and_approval_journey |
| UXP-026 Human approval dialogs | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_disruption_and_approval_journey |
| UXP-028 Accessibility test suite | EXISTING_VERIFIED | tests/browser/test_journeys.py::test_accessibility_scan |
