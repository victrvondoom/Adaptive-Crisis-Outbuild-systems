# Benchmark Methodology — AIDNEXUS ONE

## 1. Purpose

Provide reproducible, quantitative evidence that the AIDNEXUS optimization and replanning system produces measurably better humanitarian outcomes than naive allocation strategies.

**Non-goal**: Prove absolute superiority. Some scenarios may favor simpler approaches. Report all results honestly, including cases where AIDNEXUS does not outperform baselines.

## 2. Planning Modes Under Comparison

| Mode | Description | Recovery Behavior |
|------|-------------|-------------------|
| **FIFO** (Baseline A) | First-come-first-served allocation | No replanning — affected assignments cancelled |
| **Nearest-Greedy** (Baseline B) | Priority-sorted, nearest-depot allocation | No replanning — affected assignments cancelled |
| **Static-OPT** (Baseline C) | Full optimization without replanning | No replanning — affected assignments cancelled |
| **AIDNEXUS** (Experimental) | Full optimization with event-driven recovery | Automatic replanning with commitment preservation |

## 3. Scenario Generation

### Deterministic Scenarios

All scenarios are generated from a fixed random seed for reproducibility.

```
SCENARIO PARAMETERS:
  seed:             Integer (e.g., 42, 123, 256, 789, 1024)
  request_count:    25 | 50 | 100 | 200 | 500
  depot_count:      3 (fixed for comparability)
  vehicle_count:    10 (fixed)
  volunteer_count:  12 (fixed)
  item_categories:  6 (FOOD, WATER, MEDICINE, SHELTER, HYGIENE, BLANKETS)
  region_count:     5
  critical_rate:    0.15 (15% of requests are CRITICAL priority)
  deadline_spread:  4-48 hours from creation
  inventory_scarcity: 0.7 (total inventory = 70% of total demand)
```

### Disruption Events

Applied identically to all modes:

```
DISRUPTION SCENARIO:
  trigger_time:     After 60% of assignments created
  type:             WAREHOUSE_FAILURE
  affected_depot:   Depot B (middle depot by location)
  expected_impact:  ~30% of assignments affected
```

### Scenario Matrix

| Config ID | Requests | Seed | Disruption |
|-----------|----------|------|------------|
| S-025-42  | 25       | 42   | Yes        |
| S-025-123 | 25       | 123  | Yes        |
| S-050-42  | 50       | 42   | Yes        |
| S-050-123 | 50       | 123  | Yes        |
| S-100-42  | 100      | 42   | Yes        |
| S-100-123 | 100      | 123  | Yes        |
| S-100-256 | 100      | 256  | Yes        |
| S-200-42  | 200      | 42   | Yes        |
| S-200-123 | 200      | 123  | Yes        |
| S-200-256 | 200      | 256  | Yes        |
| S-200-789 | 200      | 789  | Yes        |
| S-200-1024| 200      | 1024 | Yes        |
| S-500-42  | 500      | 42   | Yes        |
| S-500-123 | 500      | 123  | Yes        |

**Total**: 14 scenarios × 4 modes = 56 benchmark runs minimum.

## 4. Metrics

### Primary Metrics

| # | Metric | Unit | Target |
|---|--------|------|--------|
| M1 | Fulfilled requests | Count & % | Maximize |
| M2 | Critical requests fulfilled | Count & % | Maximize (highest priority) |
| M3 | Needs satisfaction rate | % (allocated / demanded) | Maximize |
| M4 | Total travel distance | km | Minimize (secondary) |
| M5 | Deadline violations | Count | Minimize |
| M6 | Planning runtime | seconds | < 10s for 100 requests (P95) |
| M7 | Replanning runtime | seconds | < 15s for 200 requests (P95) |
| M8 | Resource utilization | % (used capacity / total capacity) | Optimize |

### Integrity Metrics

| # | Metric | Unit | Target |
|---|--------|------|--------|
| M9 | Inventory constraint violations | Count | **ZERO** |
| M10 | Vehicle capacity violations | Count | **ZERO** |
| M11 | Double-dispatch incidents | Count | **ZERO** |
| M12 | Unauthorized state changes | Count | **ZERO** |
| M13 | Audit event coverage | % | **100%** |
| M14 | Completed delivery overwrites | Count | **ZERO** |

### Comparative Metrics

| # | Metric | Calculation |
|---|--------|-------------|
| M15 | Fulfillment improvement over FIFO | (AIDNEXUS_M1 - FIFO_M1) / FIFO_M1 × 100% |
| M16 | Distance improvement over Greedy | (Greedy_M4 - AIDNEXUS_M4) / Greedy_M4 × 100% |
| M17 | Recovery effectiveness | Requests recovered / Requests affected × 100% |

### Targets (Not Guarantees)

- **M15**: Target ≥ 15% fulfillment improvement over FIFO on constrained scenarios
- **M16**: Target ≥ 10% distance improvement over Greedy where comparable
- **M17**: Target ≥ 60% recovery rate after warehouse failure

## 5. Execution Protocol

```
FOR each scenario S in scenario_matrix:
    1. Generate deterministic scenario data from S.seed
    2. FOR each mode M in [FIFO, NEAREST_GREEDY, STATIC_OPT, AIDNEXUS]:
        a. Load identical scenario data
        b. Run initial allocation
        c. Record pre-disruption metrics
        d. Apply disruption event
        e. Run mode-specific recovery (or no-op for baselines)
        f. Record post-disruption metrics
        g. Validate integrity constraints
        h. Save BenchmarkRun record with all metrics
    3. Generate comparative report for scenario S
```

## 6. Reporting

### Per-Scenario Report
- Table of all 4 modes' metrics side by side
- Highlighted improvements and regressions
- Explanation of any anomalies

### Aggregate Report
- Mean, median, P95 for each metric across seeds
- Confidence intervals (where sample size allows)
- Scatter plots: fulfillment vs. distance tradeoff
- Box plots: planning time distribution
- Failure cases: scenarios where AIDNEXUS underperformed

### Statistical Rigor
- Minimum 3 seeds per scenario size for variance estimation
- Paired comparison (same scenario, different modes)
- Report standard deviation alongside mean
- Do not claim statistical significance with fewer than 10 samples per configuration

## 7. Environment Documentation

Every benchmark report must include:
- Hardware: CPU model, RAM, OS
- Python version
- OR-Tools version
- Solver configuration (time limits, thread count)
- Scenario generation parameters
- Exact commit hash of benchmark code
- Timestamp of execution

## 8. Anti-Fabrication Controls

- ❌ No hardcoded chart images
- ❌ No pre-written "expected results"
- ❌ No cherry-picked scenarios
- ✅ All metrics computed from actual optimizer outputs
- ✅ Raw solver output preserved in benchmark artifacts
- ✅ Scenario seeds and parameters are public
- ✅ Benchmark code is in repository for independent verification
- ✅ Include scenarios where AIDNEXUS does NOT outperform
