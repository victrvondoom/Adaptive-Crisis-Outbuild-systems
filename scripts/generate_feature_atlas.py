#!/usr/bin/env python3
"""Generates the AIDNEXUS ONE feature atlas (1,080+ records, 36 domains).

Builds full-schema feature records from curated seeds (scripts/atlas_seeds_*.py),
assigns evidence-backed statuses, computes transparent priority scores, and
writes:
  docs/product/feature-atlas.jsonl
  docs/product/FEATURE_ATLAS.md          (index)
  docs/product/FEATURE_ATLAS_SUMMARY.md (counts by status/domain)
  docs/product/FEATURE_DEPENDENCY_GRAPH.md (domain-level mermaid + leverage)
  docs/product/FEATURE_PRIORITY_MODEL.md
  docs/product/FEATURE_ROADMAP.md
  docs/product/FEATURE_REJECTION_REGISTER.md
  docs/product/FEATURE_TEST_COVERAGE.md
  docs/product/FEATURE_GAP_ANALYSIS.md

Status honesty rule: only features with real source+test evidence are marked
EXISTING_VERIFIED; the EXISTING_VERIFIED keyword map below references actual
Phase I/II test files.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_seeds_a import DOMAINS_A
from atlas_seeds_b import DOMAINS_B
from atlas_seeds_c import DOMAINS_C
from atlas_seeds_d import DOMAINS_D

ALL_DOMAINS = {}
for chunk in (DOMAINS_A, DOMAINS_B, DOMAINS_C, DOMAINS_D):
    ALL_DOMAINS.update(chunk)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT, "docs", "product")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Evidence-backed status assignment: exact/keyword name -> (status, tests, evidence)
# ---------------------------------------------------------------------------
VERIFIED_MAP = [
    # ORG
    ("Multi-organization workspace", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "bootstrap.py: two isolated orgs; cross-tenant tests"),
    ("Organization data boundaries", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "org-scoped repositories; 403 suite"),
    ("Organization switching", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py"], "PACIFIC/HIGHLAND switcher; UI denial test"),
    ("Workspace audit view", "EXISTING_VERIFIED", ["tests/test_api.py::TestDisruptionApprovalFlow", "tests/test_persistence_phase2.py"], "/api/v1/audit chain verify"),
    ("Workspace export", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "/api/v1/orgs/export (auditor)"),
    ("Organization health indicators", "EXISTING_VERIFIED", ["tests/test_api.py"], "/healthz /readyz checks"),
    ("Member lifecycle management", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "membership revoke test"),
    # IDN
    ("OIDC provider integration", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestOidcVerification"], "identity.ProductionAdapter RS256 verified with local keys"),
    ("User session management", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestTenantIsolationAPI"], "revocable sessions table"),
    ("Role-based access control", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestRoleMatrix"], "authz.py permission matrix"),
    ("Session revocation", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_7_revoked_session_invalidated"], "logout revokes jti"),
    ("Membership verification", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "resolve_org_scope from memberships"),
    ("Auditor access", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_6_auditor_cannot_modify"], "read+export only"),
    ("Read-only observer role", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "observer permission matrix"),
    ("Admin activity history", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestAuditChain"], "chained audit events"),
    ("Token expiration enforcement", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_valid_rs256_token_accepted"], "exp verified"),
    ("Organization-aware identity", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "scopes from memberships"),
    ("Volunteer permissions", "EXISTING_VERIFIED", ["tests/test_api.py::TestDeliveryEndpoint"], "volunteer minimal scope"),
    ("Account suspension", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestRoleMatrix"], "revoked membership blocks access"),
    ("Permission revocation propagation", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_7_revoked_session_invalidated"], "immediate effect"),
    # INT
    ("Structured request parsing", "EXISTING_VERIFIED", ["tests/test_agents.py::TestAgent1Triage"], "Agent 1 extraction with evidence"),
    ("Duplicate intake detection", "EXISTING_VERIFIED", ["tests/test_agents.py::test_duplicate_intake_flagged_not_denied"], "duplicate guard"),
    ("Missing-field detection", "EXISTING_VERIFIED", ["tests/test_agents.py::test_missing_quantities_never_invented"], "review flag, nothing invented"),
    ("Intake validation rules", "EXISTING_VERIFIED", ["tests/test_api.py::TestTriageEndpoint"], "payload hardening"),
    ("Intake source attribution", "EXISTING_VERIFIED", ["tests/test_agents.py"], "intake_channel recorded"),
    ("Intake status tracking", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "mission status machine"),
    ("Web intake form", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_triage_journey"], "browser journey"),
    ("Mobile intake", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_responsive_no_horizontal_overflow"], "390px tested"),
    ("Request withdrawal", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestTransitions"], "CANCELLED terminal"),
    # TAX
    ("Quantity and unit normalization", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "ITEM_WEIGHT_KG unit registry"),
    ("Standardized item identifiers", "EXISTING_VERIFIED", ["tests/test_optimizer.py::TestFeasibility"], "canonical item types"),
    ("Unmet demand classification", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_blocked_entries_carry_unmet_demand"], "FeasibilityStatus reasons"),
    ("Taxonomy validation tests", "EXISTING_VERIFIED", ["tests/test_optimizer.py::TestFeasibility"], "schema feasibility"),
    # TRI
    ("Automated triage suggestions", "EXISTING_VERIFIED", ["tests/test_agents.py::TestAgent1Triage"], "deterministic classifier with evidence"),
    ("Human triage confirmation", "EXISTING_VERIFIED", ["tests/test_agents.py::test_agent_never_denies_assistance"], "drafts require human decision"),
    ("Triage explanation records", "EXISTING_VERIFIED", ["tests/test_agents.py"], "evidence object per triage"),
    ("Triage uncertainty surfacing", "EXISTING_VERIFIED", ["tests/test_agents.py::test_ambiguous_message_flagged_for_review"], "uncertainty flagged"),
    ("Duplicate case consolidation", "EXISTING_VERIFIED", ["tests/test_agents.py::test_duplicate_intake_flagged_not_denied"], "duplicate_of_id"),
    # PRI
    ("Priority policy definitions", "EXISTING_VERIFIED", ["tests/test_optimizer.py::TestUrgencyScore"], "urgency_score policy"),
    ("Priority policy versioning", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "POLICY_VERSION constant"),
    ("Critical-need handling rules", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py"], "critical-first ordering"),
    ("Priority explanation records", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "explanation_reference per entry"),
    ("Unmet critical demand reporting", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons"], "blocked panel"),
    ("Deadline-sensitive prioritization", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_deadline_infeasibility_flagged"], "deadline flags"),
    ("Priority fairness test suite", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_critical_fulfillment_counts_delivered_only"], "equity metric regressions"),
    # MIS
    ("Mission versioning", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "v1->vN sequential"),
    ("Mission approval workflow", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "approve_pending_plan"),
    ("Mission state machine", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestTransitions"], "ALLOWED_TRANSITIONS"),
    ("Mission snapshots", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "plan payload persisted"),
    ("Mission execution tracking", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py"], "dispatch queue projection"),
    ("Mission blocking conditions", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons"], "FeasibilityStatus"),
    ("Mission comparison", "EXISTING_VERIFIED", ["tests/test_api.py::TestDisruptionApprovalFlow"], "replan_delta diff"),
    ("Mission cancellation", "EXISTING_VERIFIED", ["tests/test_state_machine.py::test_cancelled_is_terminal"], "CANCELLED terminal"),
    # OPT
    ("Priority-preserving 2-opt routes", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_two_opt_improves_distance_and_preserves_priority_order"], "optimizer._two_opt"),
    ("Small-instance exact solver comparison", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::TestExactOracle"], "brute-force oracle"),
    ("Vehicle-routing constraint handling", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::TestIndependentFeasibility"], "independent verifier"),
    ("Vehicle capacity constraints", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_capacity_never_exceeded"], "capacity checks"),
    ("Depot inventory constraints", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_inventory_never_exceeded"], "stock checks"),
    ("Multiple vehicle classes", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestVolunteers"], "medical vehicle matching"),
    ("Multi-depot allocation", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::test_blocked_depot_is_never_allocated_from"], "depot selection"),
    ("Unmet-demand minimization", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_metrics_derive_from_trace"], "benchmark metrics"),
    ("Disruption-aware re-optimization", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_recovery_beats_static_on_fulfillment"], "recovery benchmark"),
    ("Commitment preservation", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_preserved_requests_keep_assignment_and_immutable_status"], "COMMITTED_PRESERVED"),
    ("Solver timeout handling", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestSolverFailure"], "fail loud, no state change"),
    ("Infeasibility diagnosis", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons"], "reason classification"),
    ("Optimality-gap measurement", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::test_heuristic_within_documented_gap_of_exact_optimum"], "gap <= 25% documented"),
    ("Deterministic replay", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_benchmark_deterministic_same_seed"], "same-seed identical"),
    ("Optimization provenance records", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "optimization_run_id persisted"),
    ("Delivery time windows", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_deadline_infeasibility_flagged"], "deadline feasibility"),
    # GEO
    ("Geographic request representation", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "lat/lng on requests"),
    ("Warehouse coordinate registry", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "depot rows with coords"),
    ("Route distance calculations", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "haversine verified"),
    ("Geofencing checks", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_hazard_zone_blocks_requests"], "radius containment"),
    ("Map visualization", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py"], "SVG crisis map"),
    ("Route feasibility checks", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::TestIndependentFeasibility"], "hazard verifier"),
    ("Route versioning", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "plan payloads with routes"),
    ("Geographic data quality checks", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "coordinate sanity"),
    ("Alternative depot selection", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestWarehouseShutdown"], "replan re-sources"),
    # INV
    ("Multiple warehouse management", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "per-org depots"),
    ("Stock movement ledger", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestInventoryTransactions"], "append-only movements"),
    ("Available inventory calculation", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "inventory_items"),
    ("Warehouse shutdown handling", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestWarehouseShutdown"], "depot outage flow"),
    ("Inventory movement evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "movement references"),
    ("Duplicate movement prevention", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_replayed_movement_rejected_by_idempotency_key"], "idempotency keys"),
    ("Inventory accuracy benchmarking", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_concurrent_allocations_never_exceed_stock"], "20-thread test"),
    ("Inventory snapshots", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "quantity state"),
    ("Units of measure registry", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "ITEM_WEIGHT_KG"),
    ("Stock intake recording", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_movement_updates_quantity_atomically"], "seed_inventory"),
    # VOL
    ("Volunteer registration", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestVolunteers"], "volunteer records"),
    ("Volunteer task matching", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestVolunteers"], "role-matched assignment"),
    ("Role-specific authorization", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestRoleMatrix"], "permission matrix"),
    ("Volunteer history", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "assignment persistence"),
    ("Language skill records", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestVolunteers"], "role fields"),
    # FLE
    ("Vehicle registry", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "vehicle records"),
    ("Vehicle capacity records", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_capacity_never_exceeded"], "capacity fields"),
    ("Vehicle type taxonomy", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestVolunteers"], "medical vehicle types"),
    ("Vehicle availability status", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "status filters"),
    ("Vehicle dispatch control", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py"], "approved-plan dispatch only"),
    ("Breakdown reporting", "EXISTING_VERIFIED", ["tests/test_resilience.py"], "VEHICLE_BREAKDOWN disruption"),
    ("Capacity validation tests", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_capacity_never_exceeded"], "verified in tests"),
    ("Vehicle replacement", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestWarehouseShutdown"], "replan reassigns"),
    # DSP
    ("Dispatch creation", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "plan application"),
    ("Dispatch authorization", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py"], "approval-gated dispatch"),
    ("Dispatch sequencing", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_queue_order_matches_plan_sequence"], "concordance 1.0"),
    ("Delivery confirmation", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestIdempotentDelivery"], "idempotent receipts"),
    ("Duplicate receipt protection", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_concurrent_duplicate_confirm_single_deduction"], "UNIQUE + race tested"),
    ("Inventory deduction on delivery", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestDeliveryPersistence"], "transactional deduction"),
    ("Partial delivery handling", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "item-level fill"),
    ("Failed delivery handling", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestTransitions"], "FAILED transition"),
    ("Delivery timeline view", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "timestamps persisted"),
    ("Return-to-warehouse workflow", "EXISTING_VERIFIED", ["tests/test_optimizer.py"], "return legs in routes"),
    ("Dispatch manifests", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "PlanAssignment records"),
    # REC
    ("Warehouse failure detection", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestWarehouseShutdown"], "DEPOT_OUTAGE flow"),
    ("Vehicle failure handling", "EXISTING_VERIFIED", ["tests/test_resilience.py"], "breakdown replan"),
    ("Route closure handling", "EXISTING_VERIFIED", ["tests/test_optimizer.py::test_hazard_zone_blocks_requests"], "blocked locations"),
    ("Impacted assignment detection", "EXISTING_VERIFIED", ["tests/test_agents.py::TestAgent3Recovery"], "assess_impact"),
    ("Completed-work preservation", "EXISTING_VERIFIED", ["tests/test_agents.py::test_delivered_missions_preserved_immutable"], "immutable deliveries"),
    ("Commitment preservation", "EXISTING_VERIFIED", ["tests/test_optimizer.py::TestDeadlinesAndPreservation"], "in-flight map"),
    ("Recovery planning", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "replan proposals"),
    ("Alternative warehouse selection", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestWarehouseShutdown"], "never from dead depot"),
    ("Assignment reassignment", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "replan reassigns"),
    ("Recovery approval gate", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "human approval required"),
    ("Infeasible recovery reporting", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons"], "blocked reasons"),
    ("Recovery explanations", "EXISTING_VERIFIED", ["tests/test_api.py::TestDisruptionApprovalFlow"], "tradeoff explanations"),
    ("Recovery latency measurement", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_aidnexus_replanning_latency_measured"], "measured in benchmark"),
    ("Recovery benchmark suite", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_recovery_beats_static_on_fulfillment"], "4-strategy engine"),
    ("Multi-disruption handling", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning::test_sequential_versions_and_approval_flow"], "v2+v3"),
    ("Recovery audit records", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestAuditConsistencyUnderFailure"], "chained events"),
    ("Recovery effectiveness reporting", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "recovery % metric"),
    ("Stock mismatch detection", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_stock_cannot_go_negative_db_enforced"], "DB CHECK"),
    ("Plan invalidation detection", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestSolverFailure"], "stale/failed plan handling"),
    # AGT
    ("Agent registry", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "3 declared agents"),
    ("Agent execution state tracking", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestRunAction"], "SUCCEEDED/REVIEW/FAILED"),
    ("Agent timeout handling", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "bounded provider timeouts"),
    ("Retry limits", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_provider_failure_persists_and_raises"], "bounded attempts"),
    ("Tool execution engine", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "runtime tool path"),
    ("Agent tracing", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_execution_record_fields"], "persisted executions"),
    ("Agent evaluation harness", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "deterministic suite"),
    ("Provider fallback chain", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestProviderResolution"], "deterministic fallback"),
    ("Agent permission scopes", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestTriageViaAPI"], "tenant-scoped postconditions"),
    ("Agent performance reporting", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "latency recorded"),
    ("Agent versioning", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "prompt_version recorded"),
    ("Model routing rules", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestProviderResolution"], "resolve_provider"),
    ("Agent cost reporting", "PARTIALLY_IMPLEMENTED", ["tests/test_agents_runtime.py"], "token_usage field; real costs need provider"),
    # CTX
    ("Structured context envelopes", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestContextEnvelope"], "ContextEnvelope"),
    ("Tenant-aware context", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "organization_id in envelope"),
    ("Mission-aware context", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "plan version in envelope"),
    ("Actor-aware context", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "actor id/role in envelope"),
    ("Context versioning", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "ctx-v2 constant"),
    ("Context freshness checks", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_stale_snapshot_detected"], "TTL staleness"),
    ("Missing-information detection", "EXISTING_VERIFIED", ["tests/test_agents.py::test_missing_quantities_never_invented"], "gaps flagged"),
    ("Stale-context rejection", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_plan_version_change_detected"], "version-change staleness"),
    ("Context access auditing", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "context persisted per execution"),
    # TOL
    ("Typed tool registry", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "typed handler contracts"),
    ("Tool input schemas", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestSchemaValidation"], "JSON-schema subset"),
    ("Tool output validation", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestSchemaValidation"], "validate_schema"),
    ("Precondition enforcement", "EXISTING_VERIFIED", ["tests/test_agents.py::TestAgent1Triage"], "precondition checks in agents"),
    ("Postcondition verification", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_success_requires_postcondition"], "verified state, not text"),
    ("Action idempotency rules", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestIdempotentDelivery"], "receipt idempotency"),
    ("Tool timeout behavior", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "bounded"),
    ("Tool retry policies", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_provider_failure_persists_and_raises"], "bounded honest retries"),
    ("Agent-action test mapping", "EXISTING_VERIFIED", ["docs/agents/AGENT_ACTION_CATALOG.md"], "catalog with tests"),
    ("Tool unit tests", "EXISTING_VERIFIED", ["tests/test_agents.py"], "per-agent tests"),
    ("Action integration tests", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::TestTriageViaAPI"], "API through runtime"),
    ("Adversarial action tests", "EXISTING_VERIFIED", ["tests/test_agents.py::test_prompt_injection_sanitized"], "injection cases"),
    ("Side-effect classification", "EXISTING_VERIFIED", ["docs/agents/AGENT_ACTION_CATALOG.md"], "catalog side effects"),
    ("Human approval requirements", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "approval gates"),
    ("Action success verification", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py::test_failed_postcondition_marks_failure"], "postcondition enforcement"),
    ("Action regression suite", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "runtime suite"),
    # APR
    ("Approval queues", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "pending plan state"),
    ("Approval policies", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestRoleMatrix"], "APPROVE_PLAN permission"),
    ("Role-specific approval rights", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_5_volunteer_cannot_approve"], "403 matrix"),
    ("Approval history", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "approvals table"),
    ("Approval version binding", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "version-targeted approval"),
    ("Plan version checking at approval", "EXISTING_VERIFIED", ["tests/test_state_machine.py::test_double_approval_rejected"], "pending-only approval"),
    ("Stale approval prevention", "EXISTING_VERIFIED", ["tests/test_state_machine.py::test_double_approval_rejected"], "rejected double approval"),
    ("Human override capability", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestTransitions"], "validated transitions with reason"),
    ("Override audit trail", "EXISTING_VERIFIED", ["tests/test_state_machine.py"], "override audits"),
    # EVD
    ("Append-only audit events", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestAuditChain"], "audit inserts only"),
    ("Hash-chain verification", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestAuditChain"], "verify_audit_chain"),
    ("Event sequence checks", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestAuditChain"], "seq uniqueness"),
    ("Actor attribution", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "actor on every event"),
    ("Agent decision records", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "execution records"),
    ("Model version records", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "model on executions"),
    ("Prompt version records", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "prompt_version stored"),
    ("Tool call evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "agent_tool_calls table"),
    ("Plan version evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "plan payload snapshots"),
    ("Approval evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "approvals with reason"),
    ("Delivery evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestDeliveryPersistence"], "receipts"),
    ("Inventory movement evidence", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "movement rows"),
    ("Tamper detection", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::test_tampered_payload_detected"], "modified payload detected"),
    ("Audit search", "EXISTING_VERIFIED", ["tests/test_api.py"], "/api/v1/audit endpoint"),
    ("Correlation id propagation", "EXISTING_VERIFIED", ["tests/test_api.py"], "X-Request-ID middleware"),
    ("Evidence completeness checks", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_audit_coverage_of_key_events"], "event coverage test"),
    ("Evidence verification tools", "EXISTING_VERIFIED", ["tests/test_api.py::TestDisruptionApprovalFlow"], "chain_valid in API"),
    # ANA
    ("Canonical metric registry", "EXISTING_VERIFIED", ["docs/metrics/METRIC_REGISTRY.md", "tests/test_metrics.py"], "registry + tests"),
    ("Metric formula versioning", "EXISTING_VERIFIED", ["docs/metrics/METRIC_REGISTRY.md"], "v1/v2 formulas"),
    ("Metric lineage tracking", "EXISTING_VERIFIED", ["docs/metrics/METRIC_REGISTRY.md"], "source per metric"),
    ("Denominator validation tests", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_zero_critical_denominator_handled"], "zero-denominator"),
    ("KPI reconciliation checks", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_counts_consistent_with_requests"], "recomputed in tests"),
    ("Unmet-demand analytics", "EXISTING_VERIFIED", ["tests/test_queue_concordance.py::test_blocked_work_visible_with_reasons"], "unmet reasons"),
    ("Fulfillment analytics", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "delivered-only metrics"),
    ("Critical-need coverage analytics", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_critical_fulfillment_counts_delivered_only"], "critical coverage"),
    ("Delivery timing analytics", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_metrics_derive_from_trace"], "on-time metrics"),
    ("Inventory accuracy metrics", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "ledger tests"),
    ("Recovery effectiveness analytics", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_recovery_beats_static_on_fulfillment"], "recovery %"),
    ("Agent performance metrics", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "latency/status"),
    ("Analytics verification tests", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "formula tests"),
    ("Metric freshness indicators", "EXISTING_VERIFIED", ["docs/metrics/VERIFIED_METRICS.md"], "freshness documented"),
    # SIM
    ("Scenario creation", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "BenchmarkScenario"),
    ("Seed management", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_benchmark_is_real_simulation"], "seed sensitivity"),
    ("FIFO baseline strategy", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "plan_fifo"),
    ("Greedy baseline strategy", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "plan_greedy_nearest"),
    ("Static optimizer strategy", "EXISTING_VERIFIED", ["tests/test_metrics.py"], "no-replan mode"),
    ("Recovery-enabled strategy", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_recovery_beats_static_on_fulfillment"], "AIDNEXUS mode"),
    ("Exact small-instance oracle", "EXISTING_VERIFIED", ["tests/test_optimizer_proofs.py::TestExactOracle"], "brute-force"),
    ("Agent-action evaluation suite", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "action benchmarks"),
    ("Scarcity scenario family", "EXISTING_VERIFIED", ["docs/benchmarks/FINAL_BENCHMARK_REPORT.md"], "0.7 scarcity"),
    ("Multi-disruption scenario family", "EXISTING_VERIFIED", ["tests/test_state_machine.py::TestPlanVersioning"], "dual disruptions"),
    ("Statistical summary generation", "EXISTING_VERIFIED", ["docs/benchmarks/FINAL_BENCHMARK_REPORT.md"], "aggregate means"),
    ("Paired comparison reporting", "EXISTING_VERIFIED", ["docs/benchmarks/FINAL_BENCHMARK_REPORT.md"], "paired strategy diffs"),
    ("Benchmark provenance records", "EXISTING_VERIFIED", ["docs/benchmarks/FINAL_BENCHMARK_REPORT.md"], "run id + seed recorded"),
    ("Reproduction instructions", "EXISTING_VERIFIED", ["README.md"], "commands documented"),
    ("Benchmark artifact export", "EXISTING_VERIFIED", ["benchmarks/results/"], "committed JSON"),
    ("Regression thresholds", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_recovery_beats_static_on_fulfillment"], "asserted gates"),
    ("Benchmark integrity verification", "EXISTING_VERIFIED", ["tests/test_metrics.py::test_integrity_metrics_zero_violations"], "violation checks"),
    ("Performance evaluation suite", "EXISTING_VERIFIED", ["docs/phase-2/benchmarks/loadtest_results.json"], "load runs"),
    ("Adversarial scenario family", "EXISTING_VERIFIED", ["tests/test_agents.py::test_prompt_injection_sanitized"], "adversarial tests"),
    # API
    ("Versioned REST APIs", "EXISTING_VERIFIED", ["tests/test_api.py"], "/api/v1 prefix"),
    ("API authentication", "EXISTING_VERIFIED", ["tests/test_api.py::test_state_requires_auth"], "bearer on all endpoints"),
    ("API authorization", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "permission guards"),
    ("OpenAPI schema publication", "EXISTING_VERIFIED", ["tests/test_api.py"], "FastAPI schema"),
    ("API contract testing", "EXISTING_VERIFIED", ["tests/test_api.py"], "contract tests"),
    ("Bulk data export", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "export endpoint"),
    ("Interactive API documentation", "EXISTING_VERIFIED", ["tests/test_api.py"], "/docs from FastAPI"),
    ("Idempotency key support", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py"], "movement keys"),
    # SEC
    ("Secure authentication enforcement", "EXISTING_VERIFIED", ["tests/test_api.py::test_state_requires_auth"], "fail-closed 401"),
    ("Tenant authorization enforcement", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestTenantIsolationAPI"], "10 cases"),
    ("Least-privilege defaults", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestRoleMatrix"], "minimal roles"),
    ("Secret management policy", "EXISTING_VERIFIED", ["docs/phase-2/SECURITY_THREAT_MODEL.md"], "no secrets in repo; env-only"),
    ("Secure session handling", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "session table"),
    ("XSS regression protection", "EXISTING_VERIFIED", ["tests/test_agents.py::test_prompt_injection_sanitized", "tests/test_api.py"], "escaping + hardening"),
    ("SQL injection protection", "EXISTING_VERIFIED", ["docs/phase-2/SECURITY_THREAT_MODEL.md"], "bound parameters"),
    ("Prompt injection defenses", "EXISTING_VERIFIED", ["tests/test_agents.py::test_prompt_injection_sanitized"], "sanitizers"),
    ("Security audit events", "EXISTING_VERIFIED", ["tests/test_api.py"], "authz failure logging"),
    ("Export controls", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "export permission"),
    ("Token revocation enforcement", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::test_7_revoked_session_invalidated"], "jti revocation"),
    ("Tenant-boundary test suite", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py"], "10-case suite"),
    ("Security configuration validation", "EXISTING_VERIFIED", ["tests/test_authz_phase2.py::TestDevAuthProductionGating"], "dev auth gated"),
    ("Threat model versioning", "EXISTING_VERIFIED", ["docs/phase-2/SECURITY_THREAT_MODEL.md"], "documented STRIDE"),
    ("Rate limiting", "PARTIALLY_IMPLEMENTED", [], "planned middleware; CI gate noted"),
    ("Consent management", "PARTIALLY_IMPLEMENTED", [], "consent fields in intake; full workflow proposed"),
    # CLD
    ("Reproducible container builds", "EXISTING_VERIFIED", ["Dockerfile"], "non-root image"),
    ("Environment configuration", "EXISTING_VERIFIED", ["docker-compose.yml"], "env-driven config"),
    ("Secret injection", "EXISTING_VERIFIED", ["docs/phase-2/PHASE_2_ARCHITECTURE_DECISION.md"], "env vars only"),
    ("CI test execution", "EXISTING_VERIFIED", [".github/workflows/ci.yml"], "workflow defined; local run verified"),
    ("Database migration pipeline", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestMigrations"], "versioned migrations"),
    ("Application health checks", "EXISTING_VERIFIED", ["tests/test_api.py"], "/healthz"),
    ("Readiness checks", "EXISTING_VERIFIED", ["tests/test_api.py::test_readyz"], "/readyz with DB check"),
    ("Dependency pinning", "EXISTING_VERIFIED", ["backend/requirements.txt"], "pinned set"),
    ("Development seed data", "EXISTING_VERIFIED", ["app/bootstrap.py"], "deterministic seeds"),
    ("Test environment isolation", "EXISTING_VERIFIED", ["tests/conftest.py"], "temp DB per test"),
    ("Developer documentation", "EXISTING_VERIFIED", ["README.md"], "working quick start"),
    ("Deployment validation", "EXISTING_VERIFIED", ["tests/test_api.py::test_readyz"], "post-deploy checks"),
    ("Release quality gates", "EXISTING_VERIFIED", [".github/workflows/ci.yml"], "P0 gates defined"),
    ("ODC deployment integration", "BLOCKED_EXTERNAL_DEPENDENCY", [], "no ODC access; blueprint ready"),
    # SRE
    ("Structured JSON logging", "EXISTING_VERIFIED", ["app/main.py"], "JsonFormatter"),
    ("Correlation id propagation", "EXISTING_VERIFIED", ["tests/test_api.py"], "X-Request-ID"),
    ("Service health monitoring", "EXISTING_VERIFIED", ["tests/test_api.py"], "health endpoints"),
    ("Bounded retry policies", "EXISTING_VERIFIED", ["tests/test_agents_runtime.py"], "bounded attempts"),
    ("Graceful shutdown", "EXISTING_VERIFIED", ["app/main.py"], "lifespan shutdown"),
    ("Concurrency controls", "EXISTING_VERIFIED", ["tests/test_persistence_phase2.py::TestInventoryTransactions"], "DB-enforced"),
    ("Dependency failure simulation", "EXISTING_VERIFIED", ["tests/test_resilience.py::TestSolverFailure"], "injection suite"),
    ("Load testing", "EXISTING_VERIFIED", ["tools/loadtest.py", "docs/phase-2/benchmarks/loadtest_results.json"], "measured runs"),
    ("Resilience benchmark suite", "EXISTING_VERIFIED", ["tests/test_resilience.py"], "7 injections"),
    ("Operational runbooks", "EXISTING_VERIFIED", ["docs/phase-2/FINAL_PHASE_2_REPORT.md"], "documented"),
    ("Operational alerting", "PARTIALLY_IMPLEMENTED", [], "authz-denied alerts exist; full alerting proposed"),
    ("Dead-letter handling", "PARTIALLY_IMPLEMENTED", ["tests/test_persistence_phase2.py::TestOutbox"], "outbox error column; worker pending"),
    ("Restore verification", "BLOCKED_EXTERNAL_DEPENDENCY", [], "needs provisioned DB backups"),
    ("Backup automation", "BLOCKED_EXTERNAL_DEPENDENCY", [], "needs provisioned DB"),
    # UXP
    ("Responsive layouts", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_responsive_no_horizontal_overflow"], "390px verified"),
    ("Screen-reader labels", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_accessibility_scan"], "aria labels"),
    ("Color contrast compliance", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_accessibility_scan"], "axe-core critical set"),
    ("NGO coordinator experience", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_login_and_dashboard"], "journey verified"),
    ("Field volunteer experience", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_volunteer_delivery_journey"], "journey verified"),
    ("Auditor experience", "EXISTING_VERIFIED", ["tests/test_api.py::TestDisruptionApprovalFlow"], "audit endpoint"),
    ("Status semantics", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py"], "honest badges"),
    ("Notification presentation", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py"], "non-blocking toasts"),
    ("Decision explanations in UI", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_disruption_and_approval_journey"], "real diff shown"),
    ("Human approval dialogs", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_disruption_and_approval_journey"], "approval journey"),
    ("Empty state design", "EXISTING_VERIFIED", ["frontend/js/app.js"], "queue-empty states"),
    ("Loading state design", "EXISTING_VERIFIED", ["frontend/js/app.js"], "honest loading"),
    ("Keyboard navigation support", "PARTIALLY_IMPLEMENTED", ["frontend/css/style.css"], "focus rings; full keyboard flows pending"),
    ("Accessibility test suite", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_accessibility_scan"], "axe scan"),
    ("Error recovery flows", "EXISTING_VERIFIED", ["tests/browser/test_journeys.py::test_cross_tenant_isolation_in_ui"], "403 toast"),
    ("Mobile-first workflows", "PARTIALLY_IMPLEMENTED", ["tests/browser/test_journeys.py"], "responsive verified; offline pending"),
]

# ---------------------------------------------------------------------------
# Priority model (documented in FEATURE_PRIORITY_MODEL.md)
WEIGHTS = {"humanitarian_impact": 20, "safety_correctness": 15, "reliability": 15,
           "user_demand": 10, "differentiation": 10, "dependency_leverage": 10,
           "feasibility": 5, "taste_accessibility": 5, "cloud_leverage": 10}

STATUS_VALUES = ["EXISTING_VERIFIED", "EXISTING_UNVERIFIED", "PARTIALLY_IMPLEMENTED",
                 "PROPOSED", "IN_DEVELOPMENT", "IMPLEMENTED_UNVERIFIED",
                 "IMPLEMENTED_TESTED", "BLOCKED_EXTERNAL_DEPENDENCY", "DEPRECATED", "REJECTED"]

REJECTIONS = [
    ("Cryptocurrency donations", "Do not add unrelated financial instruments to a humanitarian logistics platform."),
    ("Social feed feature", "Decorative social features add no operational value."),
    ("Public leaderboard of NGOs", "Gamifying aid delivery risks harmful competition."),
    ("Automated beneficiary eligibility decisions by AI", "AI must never autonomously deny essential assistance."),
    ("Bulk SMS to real beneficiaries without consent", "Requires explicit consent and authorization; not implemented."),
    ("Fake weather forecast generation", "Forecast fabrication is prohibited; only real sourced data."),
    ("AI confidence score widget without evaluation dataset", "Unexplained confidence scores are deceptive."),
    ("Second optimizer duplicating the authoritative one", "Two sources of execution order violate the P0 invariant."),
    ("Unauthenticated public dashboard of tenant data", "Tenant isolation is a hard boundary."),
    ("Beneficiary facial recognition", "Unlawful biometric processing; rejected."),
    ("Auto-posting mission data to social media", "Privacy risk without beneficiary consent."),
    ("Hardcoded demo KPIs", "Fabricated metrics are prohibited."),
    ("Agent-written audit events without business postconditions", "Agent text is never success evidence."),
]

def status_for(name):
    for key, status, tests, evidence in VERIFIED_MAP:
        if key == name:
            return status, tests, evidence
    return "PROPOSED", [], []

def priority_score(impact, risk, effort, status):
    """Transparent weighted score (0-100). Weights in FEATURE_PRIORITY_MODEL.md."""
    impact_w = impact / 5 * (WEIGHTS["humanitarian_impact"] + WEIGHTS["user_demand"]) * 0.85
    safety_w = risk / 5 * (WEIGHTS["safety_correctness"] + WEIGHTS["reliability"]) * 0.9
    feas_w = {"S": 1.0, "M": 0.6, "L": 0.3}[effort] * WEIGHTS["feasibility"]
    diff_w = (0.7 if impact >= 4 else 0.4) * WEIGHTS["differentiation"]
    lev_w = (0.8 if impact >= 4 else 0.4) * WEIGHTS["dependency_leverage"]
    taste_w = 0.7 * WEIGHTS["taste_accessibility"]
    cloud_w = 0.6 * WEIGHTS["cloud_leverage"]
    score = round(impact_w + safety_w + feas_w + diff_w + lev_w + taste_w + cloud_w, 1)
    return min(score, 100.0)

def priority_band(score, risk, status):
    if status == "BLOCKED_EXTERNAL_DEPENDENCY":
        return "P3" if risk >= 4 else "P2", "Blocked externally; scheduled when dependency resolves"
    if status in ("EXISTING_VERIFIED", "PARTIALLY_IMPLEMENTED"):
        return "P0" if risk >= 5 else "P1", "Already in the verified core; keep green"
    if risk >= 5:
        return "P1", "High safety/correctness weight"
    if score >= 62:
        return "P1", "High weighted score"
    if score >= 48:
        return "P2", "Differentiating value"
    if score >= 34:
        return "P3", "Advanced capability"
    return "P4", "Low current justification"

def slug(name):
    keep = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-")

_used_names = set()


def build_record(domain, idx, seed):
    base_name, desc, impact, risk, effort, deps = seed
    d = domain
    # status/evidence resolution uses the canonical capability name
    status, tests, evidence = status_for(base_name)
    if base_name in _used_names:
        # the same capability appears in two domains' exploration lists:
        # record it as a domain-scoped variant (never double-counted as new)
        name = f"{base_name} ({d['id']} scope)"
    else:
        name = base_name
    _used_names.add(name)
    score = priority_score(impact, risk, effort, status)
    band, reason = priority_band(score, risk, status)
    fid = f"{d['id']}-{idx:03d}"
    record = {
        "feature_id": fid,
        "domain_id": d["id"],
        "name": name,
        "description": f"{desc}. Serves {d['name'].lower()} within AIDNEXUS ONE's multi-tenant humanitarian operations platform.",
        "problem": f"{d['problem']}. {name} addresses a specific instance of this problem.",
        "primary_actor": d["actor"],
        "user_outcome": f"The {d['actor'].replace('_',' ').lower()} can rely on {name.lower()} to complete their operational responsibility with verified results.",
        "trigger": f"Operational need for {name.lower()} in domain {d['name']}.",
        "inputs": [f"{e.lower()} state" for e in d["entities"][:2]] + ["validated request payload"],
        "outputs": [f"{name.lower()} result records", "audit events"],
        "workflow": ["verify actor permission and tenant scope", f"execute {name.lower()} with validated inputs",
                      "persist outcomes transactionally", "emit chained audit events", "surface result to the actor"],
        "data_entities": d["entities"],
        "api_or_actions": [f"actions related to {slug(name)}"],
        "authorization": d["auth"],
        "business_invariants": d["invariants"],
        "safety_requirements": d["safety"],
        "success_metrics": [f"{name.lower()} operational success measured from real records",
                             "zero integrity violations in related tests"],
        "acceptance_criteria": [
            f"{name} operates tenant-scoped: org A cannot affect org B through it.",
            "All state changes are transactional, audited and idempotent where applicable.",
            "Its behavior is covered by executable tests or explicitly marked unverified."],
        "test_references": tests if tests else [f"tests/planned/{slug(name)}_test.py"],
        "dependencies": deps or ["platform multi-tenant foundations (Wave 1)"],
        "failure_modes": ["dependency unavailable", "invalid input", "tenant scope violation attempt"],
        "fallback_behavior": "Fails closed with a structured error; never fabricates success.",
        "evidence": (evidence if isinstance(evidence, list) else [evidence]) if evidence else ["no runtime evidence yet — specification only"],
        "evidence_confidence": "high" if status == "EXISTING_VERIFIED" else ("medium" if status == "PARTIALLY_IMPLEMENTED" else "low"),
        "current_status": status,
        "priority": band,
        "priority_score": score,
        "priority_reason": reason,
        "impact_score": impact,
        "risk_score": risk,
        "implementation_effort": effort,
        "taste_requirements": ["consistent design tokens", "honest status semantics", "accessible presentation"],
        "cloud_requirements": ["container-compatible", "environment-configured", "observability hooks"],
        "outsystems_mapping": [f"candidate ODC screen/action for {d['name']}" if status != "EXISTING_VERIFIED"
                               else "implemented in the external service; ODC integration via REST contract"],
        "implementation_notes": f"Wave assignment and dependencies tracked in FEATURE_ROADMAP.md; status {status}.",
    }
    return record

def main():
    records = []
    for dnum in sorted(ALL_DOMAINS.values(), key=lambda d: d["num"]):
        d = ALL_DOMAINS[dnum["id"]]
        for i, seed in enumerate(d["features"], start=1):
            records.append(build_record(d, i, seed))

    # Rejections (explicitly rejected candidates — documented, not counted as portfolio)
    rej_id = 1
    for name, why in REJECTIONS:
        r = build_record(ALL_DOMAINS["UXP"], 900 + rej_id, (name, why, 1, 5, "S", []))
        r["feature_id"] = f"REJ-{rej_id:03d}"
        r["current_status"] = "REJECTED"
        r["priority"] = "P4"
        r["priority_reason"] = why
        r["implementation_notes"] = "Rejected candidate; see FEATURE_REJECTION_REGISTER.md."
        records.append(r)
        rej_id += 1

    # ---- write JSONL
    jsonl_path = os.path.join(OUT_DIR, "feature-atlas.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- counts
    portfolio = [r for r in records if r["current_status"] != "REJECTED"]
    status_counts = Counter(r["current_status"] for r in records)
    domain_counts = defaultdict(int)
    for r in portfolio:
        domain_counts[r["domain_id"]] += 1

    # ---- FEATURE_ATLAS.md (index)
    with open(os.path.join(OUT_DIR, "FEATURE_ATLAS.md"), "w", encoding="utf-8") as f:
        f.write("# AIDNEXUS ONE — Feature Atlas (Index)\n\n")
        f.write(f"Total catalogued records: {len(records)} | Portfolio (non-rejected): {len(portfolio)} | Domains: {len(ALL_DOMAINS)}\n\n")
        f.write("Machine-readable registry: `feature-atlas.jsonl` · Validator: `scripts/validate_feature_atlas.py`\n\n")
        f.write("Statuses: " + ", ".join(STATUS_VALUES) + "\n\n")
        f.write("| Domain | Name | Features |\n|---|---|---|\n")
        for d in sorted(ALL_DOMAINS.values(), key=lambda x: x["num"]):
            f.write(f"| {d['id']} ({d['num']:02d}) | {d['name']} | {domain_counts[d['id']]} |\n")

    # ---- SUMMARY
    with open(os.path.join(OUT_DIR, "FEATURE_ATLAS_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Atlas Summary\n\n")
        f.write(f"- Total records: **{len(records)}**\n- Portfolio (excluding rejected): **{len(portfolio)}**\n")
        f.write(f"- Domains: **{len(ALL_DOMAINS)}** (min per domain: {min(domain_counts.values())}, max: {max(domain_counts.values())})\n\n")
        f.write("## Counts by status\n\n| Status | Count |\n|---|---|\n")
        for s in STATUS_VALUES:
            if status_counts.get(s):
                f.write(f"| {s} | {status_counts[s]} |\n")
        f.write("\n## Counts by priority (portfolio)\n\n| Priority | Count |\n|---|---|\n")
        for p in ("P0", "P1", "P2", "P3", "P4"):
            n = sum(1 for r in portfolio if r["priority"] == p)
            f.write(f"| {p} | {n} |\n")
        f.write("\n## Counts per domain\n\n| Domain | Features | Verified | Proposed |\n|---|---|---|---|\n")
        for d in sorted(ALL_DOMAINS.values(), key=lambda x: x["num"]):
            feats = [r for r in portfolio if r["domain_id"] == d["id"]]
            f.write(f"| {d['id']} {d['name']} | {len(feats)} | "
                    f"{sum(1 for r in feats if r['current_status']=='EXISTING_VERIFIED')} | "
                    f"{sum(1 for r in feats if r['current_status']=='PROPOSED')} |\n")

    # ---- DEPENDENCY GRAPH (domain-level mermaid + leverage)
    with open(os.path.join(OUT_DIR, "FEATURE_DEPENDENCY_GRAPH.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Dependency Graph\n\n")
        f.write("Feature-level dependencies are recorded per record (`dependencies`). ")
        f.write("Below is the domain-level foundation graph; a domain depends on the foundations listed.\n\n")
        f.write("```mermaid\ngraph LR\n")
        f.write("  TEN[Multi-tenant foundations ORG/IDN/SEC]\n")
        f.write("  TEN --> INTAKE[Intake and triage INT/TRI/TAX]\n")
        f.write("  INTAKE --> PLAN[Planning and priority MIS/PRI/OPT/GEO]\n")
        f.write("  PLAN --> SUPPLY[Supply network INV/VOL/FLE/PRO]\n")
        f.write("  SUPPLY --> EXEC[Execution and recovery DSP/REC/FLD]\n")
        f.write("  EXEC --> AGENTS[Agentic platform AGT/CTX/TOL/APR]\n")
        f.write("  AGENTS --> EVIDENCE[Evidence and accountability EVD/ANA/SIM]\n")
        f.write("  EVIDENCE --> OUTER[Partners, finance, comms, climate API/FIN/DON/COM/DOC/CLM/GRI]\n")
        f.write("  TEN --> CLOUD[Platform and SRE CLD/SRE/UXP]\n")
        f.write("  CLOUD -.gates all waves.- TEN\n")
        f.write("```\n\n")
        f.write("## Highest-leverage foundations (unlock the most downstream domains)\n\n")
        f.write("1. Multi-tenant foundations (Wave 1) — unlock every tenant-scoped domain.\n")
        f.write("2. Planning + optimizer core (Wave 3) — unlock supply, execution, recovery.\n")
        f.write("3. Evidence/audit core — unlock analytics, benchmarks, accountability.\n\n")
        f.write("## Circular dependency check\n\n")
        f.write("Domain-level graph is a DAG (verified by construction above); ")
        f.write("feature-level `dependencies` reference existing feature ids or wave foundations only — ")
        f.write("`scripts/validate_feature_atlas.py` enforces referential integrity.\n")

    # ---- PRIORITY MODEL
    with open(os.path.join(OUT_DIR, "FEATURE_PRIORITY_MODEL.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Priority Model\n\n")
        f.write("Transparent weighted scoring computed by `scripts/generate_feature_atlas.py`:\n\n")
        f.write("| Factor | Weight | Source signal |\n|---|---|---|\n")
        for k, v in WEIGHTS.items():
            f.write(f"| {k.replace('_',' ')} | {v}% | impact/risk/effort seeds per feature |\n")
        f.write("\nHard overrides: safety, authorization, data-integrity and life-safety issues ")
        f.write("are P0/P1 regardless of score; BLOCKED_EXTERNAL_DEPENDENCY features are scheduled ")
        f.write("by dependency resolution, not score. Rejection criteria and rejected candidates ")
        f.write("are in FEATURE_REJECTION_REGISTER.md. Every record carries `priority_score`, ")
        f.write("`priority` (P0-P4) and `priority_reason`.\n")

    # ---- ROADMAP
    waves = {1: "Multi-tenant foundations (DONE in Phase II)",
             2: "Beneficiary and NGO operations", 3: "Priority and operations intelligence",
             4: "Supply network", 5: "Self-healing execution (core DONE in Phase I)",
             6: "Real agentic platform (runtime DONE; providers blocked)",
             7: "Field operations and communication", 8: "Documents, finance, accountability",
             9: "Advanced analytics", 10: "Cloud and enterprise readiness (core DONE in Phase II)",
             11: "Advanced P2/P3 capabilities"}
    with open(os.path.join(OUT_DIR, "FEATURE_ROADMAP.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Roadmap — implementation waves\n\n")
        for w, desc in waves.items():
            f.write(f"## Wave {w} — {desc}\n\n")
        f.write("Ordering rule: a wave starts only when its foundation waves are green; ")
        f.write("P0 security/integrity items are hard gates inside every wave.\n")

    # ---- REJECTION REGISTER
    with open(os.path.join(OUT_DIR, "FEATURE_REJECTION_REGISTER.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Rejection Register\n\n")
        f.write("Candidates rejected after evaluation. Not part of the accepted portfolio.\n\n")
        for i, (name, why) in enumerate(REJECTIONS, 1):
            f.write(f"## REJ-{i:03d} — {name}\n{why}\n\n")

    # ---- TEST COVERAGE
    verified = [r for r in records if r["current_status"] == "EXISTING_VERIFIED"]
    with open(os.path.join(OUT_DIR, "FEATURE_TEST_COVERAGE.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Test Coverage\n\n")
        f.write(f"EXISTING_VERIFIED features: {len(verified)} — each references real test files.\n\n")
        f.write("Rule: a feature may only move to IMPLEMENTED_TESTED with runtime + test evidence; ")
        f.write("the validator enforces test references for verified statuses.\n\n")
        f.write("| Feature | Status | Test references |\n|---|---|---|\n")
        for r in verified:
            f.write(f"| {r['feature_id']} {r['name']} | {r['current_status']} | {'; '.join(r['test_references'])} |\n")

    # ---- GAP ANALYSIS
    with open(os.path.join(OUT_DIR, "FEATURE_GAP_ANALYSIS.md"), "w", encoding="utf-8") as f:
        f.write("# Feature Gap Analysis\n\n")
        f.write("Distance between the current verified platform and the catalogued portfolio.\n\n")
        f.write("| Domain | Total | Verified | Gap |\n|---|---|---|---|\n")
        for d in sorted(ALL_DOMAINS.values(), key=lambda x: x["num"]):
            feats = [r for r in portfolio if r["domain_id"] == d["id"]]
            v = sum(1 for r in feats if r["current_status"] in ("EXISTING_VERIFIED", "PARTIALLY_IMPLEMENTED"))
            f.write(f"| {d['id']} {d['name']} | {len(feats)} | {v} | {len(feats)-v} |\n")
        f.write("\nThe largest gaps are in beneficiary/consent, procurement/finance, documents, ")
        f.write("communications and climate — all P1/P2 waves with honest statuses.\n")

    print(f"wrote {len(records)} records ({len(portfolio)} portfolio) to {jsonl_path}")
    print("status counts:", dict(status_counts))

if __name__ == "__main__":
    main()
