# Phase VI — Baseline Verification (2026-11-02)

| Check | Result |
|---|---|
| Starting branch | `claude/elegant-brahmagupta-x93pr4` @ `6359ade` ("Submission sprint…"); working tree clean |
| Phase VI branch | `phase-6-advanced-system-design` created from it. No history reset, no user changes discarded. |
| Phase V present? | **Yes — verified by evidence, not by prompt.** `frontend/js/system-design-data.js` holds 20 topics; `resilience_patterns.py`, `scheduler.py`, migration v4 exist; `docs/system-design/*` exists. |
| Baseline tests | `pytest -m "not browser"`: **256 passed**; 11 browser journeys exist (run later: pass) |
| Backend / DB | FastAPI; SQLAlchemy 2; SQLite WAL (dev/test); PostgreSQL via `DATABASE_URL` (psycopg) is the *prod path* — **no PostgreSQL server exists in this sandbox** (only the `psql` client), so no PostgreSQL behaviour was measured |
| Frontend | vanilla JS SPA, no build step; Studio tab with Topics/Map/Trace/Lab |
| Deployment infra | Dockerfile + compose only. Nothing deployed anywhere. |
| External services | none configured (no LLM, SMS, storage, KMS keys) |
| OutSystems | spec documents only; no ODC app (unchanged — NOT_IMPLEMENTED per CURRENT_STATE) |
| Existing benchmarks | `benchmarks/results/*` (optimizer strategies, Phase II–IV) untouched |
| Competition gate | Kickoff 2026-11-02 00:00 UTC (docs/competition-compliance.md); build window is open today. Local work only; no deploy, no publishing. |
| Environment limits | Outbound network allow-list excludes w3.org, postgresql.org, sqlite.org → vendor-doc verification could not be performed (see REFERENCES) |
| Env quirk | Playwright upgraded by `pip install -r requirements.txt`; pre-installed Chromium used via `/opt/pw-browsers/chromium` (browser tests only) |
