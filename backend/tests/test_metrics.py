"""Metric formula tests: every displayed KPI is computed from underlying
state with the documented numerator/denominator (docs/metrics/METRIC_REGISTRY.md)."""
import pytest
from app.models import PriorityLevel, MissionStatus
from app.benchmark import run_single_benchmark


class TestDashboardMetrics:
    def test_critical_fulfillment_counts_delivered_only(self, engine):
        """Regression: the old formula counted DISPATCHED as fulfilled and
        showed 100% while nothing was delivered."""
        stats = engine.get_summary_state()["stats"]
        all_reqs = list(engine.requests.values())
        crit_total = sum(1 for r in all_reqs if r.priority == PriorityLevel.CRITICAL)
        crit_delivered = sum(1 for r in all_reqs
                             if r.priority == PriorityLevel.CRITICAL
                             and r.status == MissionStatus.DELIVERED)
        expected = round(crit_delivered / crit_total * 100, 1) if crit_total else 0.0
        assert stats["critical_fulfillment_rate"] == expected
        # explicit regression guard: dispatched ≠ fulfilled
        assert stats["critical_fulfillment_rate"] < 100.0 or crit_delivered == crit_total

    def test_zero_critical_denominator_handled(self, engine):
        engine.requests = {k: v for k, v in engine.requests.items()
                           if v.priority != PriorityLevel.CRITICAL}
        stats = engine.get_summary_state()["stats"]
        assert stats["critical_fulfillment_rate"] == 0.0  # NOT a divide-by-zero

    def test_counts_consistent_with_requests(self, engine):
        s = engine.get_summary_state()["stats"]
        all_reqs = list(engine.requests.values())
        assert s["total_requests"] == len(all_reqs)
        assert s["delivered_count"] == sum(1 for r in all_reqs
                                           if r.status == MissionStatus.DELIVERED)
        assert s["dispatched_count"] == sum(1 for r in all_reqs
                                            if r.status == MissionStatus.DISPATCHED)

    def test_queue_concordance_metric(self, engine):
        assert engine.queue_concordance() == 1.0

    def test_state_returns_all_requests(self, engine):
        """Regression: /state used to truncate 200 -> 140 silently."""
        s = engine.get_summary_state()
        assert len(s["requests"]) == len(engine.requests) == 200


class TestBenchmarkMetrics:
    def test_benchmark_is_real_simulation(self):
        """Regression: the old benchmark returned identical constants for
        every seed. The real engine must produce seed-sensitive results."""
        r42 = run_single_benchmark(seed=42, n_requests=60)
        r999 = run_single_benchmark(seed=999, n_requests=60)
        assert r42["metrics"] != r999["metrics"]

    def test_benchmark_deterministic_same_seed(self):
        def strip(ms):
            return [{k: v for k, v in m.items()
                     if k not in ("replan_latency_seconds", "planning_time_seconds")}
                    for m in ms]
        a = run_single_benchmark(seed=42, n_requests=60)
        b = run_single_benchmark(seed=42, n_requests=60)
        assert strip(a["metrics"]) == strip(b["metrics"])

    def test_integrity_metrics_zero_violations(self):
        """No strategy may accept hard-constraint violations."""
        r = run_single_benchmark(seed=42, n_requests=60)
        for m in r["metrics"]:
            assert m["inventory_violations"] == 0
            assert m["capacity_violations"] == 0
            assert m["duplicate_dispatches"] == 0

    def test_metrics_derive_from_trace(self):
        """fulfilled + unmet == total; critical % consistent with counts."""
        r = run_single_benchmark(seed=42, n_requests=60)
        for m in r["metrics"]:
            assert m["fulfilled_count"] + m["unmet_demand_count"] == m["total_requests"]
            if m["critical_total"]:
                expected = round(m["critical_fulfilled_count"] / m["critical_total"] * 100, 1)
                assert m["critical_fulfilled_pct"] == expected

    def test_aidnexus_replanning_latency_measured(self):
        r = run_single_benchmark(seed=42, n_requests=60)
        aidn = [m for m in r["metrics"] if m["strategy_name"].startswith("AIDNEXUS")][0]
        assert aidn["replan_latency_seconds"] >= 0
        baselines = [m for m in r["metrics"] if not m["strategy_name"].startswith("AIDNEXUS")]
        assert all(m["replan_latency_seconds"] == 0.0 for m in baselines)  # no replanning

    def test_recovery_beats_static_on_fulfillment(self):
        """Core product claim, verified honestly: replanning must not be
        worse than not replanning on the same scenario."""
        for seed in (42, 123, 256):
            r = run_single_benchmark(seed=seed, n_requests=60)
            aidn = [m for m in r["metrics"] if m["strategy_name"].startswith("AIDNEXUS")][0]
            static = [m for m in r["metrics"] if m["strategy_name"].startswith("Static")][0]
            assert aidn["fulfilled_count"] >= static["fulfilled_count"], \
                f"seed {seed}: replanning underperformed static planning"
            assert aidn["disruption_resilience_score"] > static["disruption_resilience_score"]


class TestAuditChainMetric:
    def test_audit_coverage_of_key_events(self, engine):
        types = {e.event_type for e in engine.audit_events}
        assert "SCENARIO_RESET" in types
        assert "PLAN_INITIALIZED" in types
        assert "DELIVERY_CONFIRMED" in types
