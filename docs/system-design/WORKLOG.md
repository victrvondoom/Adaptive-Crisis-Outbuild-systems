# Worklog — Phase V

- **M0** — Verified baseline (222 tests + 10 journeys green, clean tree,
  `0fffb83` ancestry). Created `phase-5-system-design-visual`.
- **M1** — Decision matrix for all 20 topics with honest classes (A–E) and
  evidence pointers; explicitly rejected K8s/Kafka/Redis/2PC/event-sourcing.
- **M8 code** — `resilience_patterns.py` (TokenBucket/RateLimiter,
  CircuitBreaker, retry_with_backoff); rate-limit middleware in main.py
  (found+fixed the exempt-path bug); breaker + full-jitter backoff wired
  into the LLM provider path; outbox DLQ (5 attempts, preserved errors);
  `scheduler.py` + migration v4 + scheduler endpoints (found+fixed SQLite
  nested-lock and naive-datetime bugs).
- **Tests** — 34 new backend tests across 3 files; conftest limiter reset;
  suite 256 green.
- **M2-7 Studio** — `system-design-data.js` (20 topics × full field set,
  honest statuses; architecture map of the ACTUAL topology; real request
  trace), `system-design-studio.js` (chapters, topic pages, map, trace,
  REAL/SIMULATED failure lab, light/dark theme), tab + CSS, keyboard nav
  and aria labels.
- **M9-10** — Browser journey for the Studio (11/11 green) with screenshot;
  failure lab: 3 REAL live scenarios + 2 SIMULATED (test-backed).
- **M11-12** — system-design docs (decision matrix, overview, implementation
  and test matrices, failure lab, references with verification status,
  execution state, decision log, open issues, test evidence).
- **Final** — Commit with Mistral Vibe as author; push to the GitHub remote.
