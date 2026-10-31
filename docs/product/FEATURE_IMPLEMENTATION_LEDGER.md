# Feature Implementation Ledger

Status changes require evidence; every entry lists commit, files, tests, verification.

| Feature | Commit | Files changed | Tests | Runtime verification | Status |
|---|---|---|---|---|---|
| INV-006 Expiry tracking | (this Phase III commit) | app/migrations/versions/v2.py, app/persistence_phase3.py, app/main.py, app/models_db.py | tests/test_phase3_features.py::TestInventoryExpiry (3 tests) | API set+report; window filtering; tenant scope; volunteer 403 | IMPLEMENTED_TESTED |
| VOL-011 Certification expiry tracking | (this Phase III commit) | same migration/models/persistence | tests/test_phase3_features.py::TestCertificationExpiry (2 tests) | set + expired report; valid certs excluded | IMPLEMENTED_TESTED |
| APR-006 Approval delegation | (this Phase III commit) | app/persistence_phase3.py, app/main.py (guard) | tests/test_phase3_features.py::TestApprovalDelegation (4 tests) | temporary grant, revocation, holder-only, tenant scope | IMPLEMENTED_TESTED |
| EVD-022 Audit search | (this Phase III commit) | app/main.py | tests/test_phase3_features.py::TestAuditSearch (2 tests) | type/contains filters; chain_valid always returned | IMPLEMENTED_TESTED |
| TRI-011 Case notes | (this Phase III commit) | app/persistence_phase3.py, app/main.py | tests/test_phase3_features.py::TestCaseNotes (3 tests) | audited notes; content isolation across tenants | IMPLEMENTED_TESTED |

Known limitations: delegation grant is logged as a structured auth event (not yet in the
per-org audit chain); case notes are plain text (attachments are a separate proposed feature).
