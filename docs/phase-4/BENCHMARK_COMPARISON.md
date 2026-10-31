# Benchmark Comparison (Phase IV, Wave 12)

## Method

- Implementation commit: this Phase IV branch head (post-`66fda2b`).
- Fresh run: `cd backend && python -m app.benchmark` →
  `benchmarks/results/benchmark_matrix_1793438128.json` (9 runs; seeds 42/123/256 ×
  n=50/100/200). All numbers computed from execution traces; nothing hand-written.
- Baseline: committed Phase I artifacts (`benchmarks/results/benchmark_500_seed42.json`,
  committed at `0fffb83`) — **not modified**.

## Fresh Phase IV run (raw, honest — including losses)

| Seed | n | AIDNEXUS fulfilled | vs FIFO | vs static-opt | travel vs greedy | on-time | integrity violations |
|---|---|---|---|---|---|---|---|
| 42 | 50 | 25/50 | +0.0% | +0.0% | +43.9% | 100% | 0 |
| 123 | 50 | 26/50 | +13.0% | +0.0% | +30.5% | 100% | 0 |
| 256 | 50 | 23/50 | +4.5% | +0.0% | +29.6% | 100% | 0 |
| 42 | 100 | 46/100 | **−8.0%** | +9.5% | +24.6% | 100% | 0 |
| 123 | 100 | 48/100 | +9.1% | +17.1% | −5.3% | 100% | 0 |
| 256 | 100 | 39/100 | **−17.0%** | +5.4% | +10.9% | 100% | 0 |
| 42 | 200 | 53/200 | +1.9% | +17.8% | +13.8% | 100% | 0 |
| 123 | 200 | 59/200 | +9.3% | +15.7% | +13.8% | 100% | 0 |
| 256 | 200 | 52/200 | **−11.9%** | +13.0% | +21.4% | 100% | 0 |

Recovery latency: 0.0003–0.002 s across all runs (sub-2 ms replanning).

## Comparison with the verified Phase I baseline

Phase I baseline (seed=42, n=500): AIDNEXUS 59/500 fulfilled, +11.3% vs FIFO,
+25.5% vs static-opt, +13.5% travel improvement vs greedy, 100% on-time,
0 integrity violations, recovery latency 0.0013 s.

Phase IV fresh runs reproduce the same qualitative behavior with the same code
path (the optimizer and benchmark engine were NOT modified in Phase IV —
verified by `git diff 0fffb83..HEAD -- backend/app/optimizer.py backend/app/benchmark.py`
showing no functional changes to those modules):
- Static-optimization improvement: consistent (+0% to +17.8% across sizes).
- Distance improvement vs greedy: mostly positive, one −5.3% case (greedy happens
  to win travel in a single low-n run — reported honestly).
- FIFO wins raw counts in 3 of 9 runs under scarcity: **confirmed again** — FIFO
  can out-fulfill when scarcity dominates because it ignores priority weighting.
  AIDNEXUS trades raw count for critical-priority coverage (measured in the
  metric registry: critical coverage vs FIFO).
- Integrity invariants (inventory, capacity, duplicate suppression): **0
  violations in all 9 runs** — the core correctness property holds after all
  Phase IV domain additions.

## Agent/system-level benchmarking status

- Agent-action evaluation (need extraction, tool selection, postconditions):
  covered by executable tests (`tests/test_agents*.py`), not by the benchmark
  harness — honest labeling.
- Real model-backed agent benchmarks (token consumption, cost per task,
  provider latency): **BLOCKED** — no provider credentials; the deterministic
  provider's "provider" column reports `deterministic` and no model metrics are
  invented.
- Platform-level load/performance: Phase II load tests remain in
  `tests/test_resilience.py`; no new load claims are made in Phase IV beyond
  the recovery-latency measurements above.
