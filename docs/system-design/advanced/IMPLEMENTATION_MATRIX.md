# Implementation Matrix

| Topic | Code | Tests |
|---|---|---|
| 21 | models_db.py, advanced_lab.integrity_probe | test_phase6_database::integrity |
| 22 | migrations/v5.py, models_db indexes, advanced_lab.index_experiment | test_phase6_database::index*, migration* |
| 23 | persistence.apply_inventory_movement (existing), advanced_lab.inventory_contention | contention tests |
| 24 | db.build_engine, advanced_lab.pool_* | pool tests |
| 25,26,27,39 | advanced_lab_ext (sims) | test_phase6_consistency_locks |
| 28 | scheduler.claim_job/finish_job_in, v5 fence | stale-holder regression, lease tests, test_scheduler |
| 30 | object_store.py | test_phase6_storage_secrets |
| 31 | main.request_context no-store | observability header tests |
| 32,33,34,35,40 | advanced_lab_ext | consistency_locks tests |
| 36,37 | telemetry.py, main.py endpoints | test_phase6_observability |
| 38 | keyring.py | storage_secrets tests |
UI: frontend/js/system-design-advanced*.js; browser: tests/browser/test_phase6_studio.py.
