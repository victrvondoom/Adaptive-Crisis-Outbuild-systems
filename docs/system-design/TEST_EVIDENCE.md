# Test Evidence — Phase V

Run on branch `phase-5-system-design-visual` at the final Phase V commit.

```bash
cd backend
python -m pytest                          # 256 passed, 11 deselected (browser)
python -m pytest tests/browser -m browser # 11/11 journeys, real Chromium
node --check frontend/js/app.js            # + studio JS files: OK
python scripts/validate_feature_atlas.py   # ATLAS VALID
ruff check app tests --select E9,F63,F7,F82,F401 --ignore F401  # pass
```

## New tests this phase (34 backend + 1 browser)

- `tests/test_rate_limiter.py` (15): bucket semantics (burst/refill/retry-
  after), scope independence, API 429 contract, tenant quota isolation,
  anonymous limits, expensive-endpoint budget, health exemptions.
- `tests/test_resilience_patterns.py` (10): breaker CLOSED→OPEN→HALF_OPEN→
  CLOSED incl. fail-fast + probe admission + reopen; retry classification,
  max attempts, deadline; full-jitter bounds; poison-message dead-letter.
- `tests/test_scheduler.py` (9): first-tick runs, duplicate no-op, force+idle
  idempotence, locked skip, failure recorded + retried, UTC, API permissions.
- `tests/browser/test_journeys.py::test_system_design_studio_journey`:
  20 topics render, topic detail + quiz reveal, map inspection, trace steps,
  REAL scheduler duplicate-trigger lab, theme toggle. Screenshot:
  `docs/phase-2/screenshots/system_design_studio.png`.

## Regressions fixed during development (honest record)

1. Rate-limiter exempt-path tuple matched EVERY path (`"/"` prefix) — the
   limiter was a no-op; caught by tests, fixed (V10 in DECISION_LOG).
2. Scheduler nested write sessions caused SQLite lock errors + naive
   datetime comparisons — restructured claim/execute phases, `_aware()` UTC
   normalization.
3. Test-suite-wide 429s from org-bucket accumulation — conftest now resets
   the limiter per test (proper isolation, documented).
