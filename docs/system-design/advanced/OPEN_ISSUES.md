# Open Issues
- O-1 (P2) cross-tenant inventory row accepted by DB (composite FK needed).
- O-2 PostgreSQL never exercised: isolation, EXPLAIN, pool exhaustion, PITR unmeasured.
- O-3 Telemetry in-memory only; SLI window = process lifetime.
- O-4 Restore drill lacks plan-checksum, receipt-integrity, app-restart checks.
- O-5 Object store unwired; no malware scanning, KMS.
- O-6 Vendor/standard references unverified (network allow-list).
- O-7 `DB_POOL_*` defaults untuned.
- O-8 Pre-existing: `/favicon.ico` returns 404.
- O-9 Browser tests need a Chromium matching Playwright (handled via PW_CHROMIUM_PATH / /opt/pw-browsers).
