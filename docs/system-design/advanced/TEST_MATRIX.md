# Test Matrix (Phase VI)

| Condition | Test |
|---|---|
| Referential integrity / duplicates / negative stock / idempotency / deletion | test_integrity_probe_all_checks_hold |
| Migration fresh / upgrade / idempotent | test_migration_v5_*, test_v5_upgrades_a_pre_v5_database |
| Index used, results identical | test_index_experiment_adopts_only_evidence_supported_indexes |
| Concurrent updates / rollback | test_concurrent_inventory_* |
| Pool saturation, budget, env | test_pool_*, test_postgres_pool_env_is_bounded |
| Stale lock holder, expiry, mutual exclusion | test_stale_holder_*, test_lease_* (regression fails without fence — verified by mutation) |
| Stale replica / partition / failover | test_replica_routing_*, test_cap_partition_* |
| Reconnect, duplicates, stale, restart, retention | test_event_stream_*, test_event_log_retention_forces_resync |
| Slow consumer / cancel | test_backpressure_policies |
| Search lag/delete/tenant/duplicate/failure | test_search_index_properties |
| Expand/backfill/interrupt/contract | test_schema_evolution_lab |
| Trace propagation / missing id / error class / sampling / redaction / instrumentation failure | test_phase6_observability |
| Storage authz / expiry / cross-tenant / corruption / duplicate / delete | test_phase6_storage_secrets |
| Secrets rotation / revoke / missing | test_keyring_*, test_missing_secret_* |
| SLI exclusions / budget math / NOT_MEASURED | observability tests |
| Backup/restore invariants | test_backup_restore_validates_everything |
| UI | tests/browser/test_phase6_studio.py (+11 existing journeys) |
Not tested: PostgreSQL behaviour, process kill durability, real network partitions.
