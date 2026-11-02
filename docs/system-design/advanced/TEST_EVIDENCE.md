# Test Evidence
- Baseline (before changes): `pytest -m "not browser"` → 256 passed.
- Final: **307 passed** (51 new in 4 `test_phase6_*` files), 0 failed.
- Browser (`-m browser`): **13 passed** (11 existing + 2 Phase VI: full advanced journey incl. real lab via API, quiz, explorer, telemetry; mobile no horizontal overflow). Screenshots: docs/phase-6/screenshots/.
- Mutation check: removing the fence predicate fails `test_stale_holder_cannot_overwrite_or_release` and `test_lease_fencing_lab`.
- Benchmarks: benchmarks/phase6/phase6_lab_eb6644c.json (invariants held every run).
- Findings from running things: rowcount artifact in my index lab; tautological invariants; mobile overflow; Playwright/browser mismatch.
