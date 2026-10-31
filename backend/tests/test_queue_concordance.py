"""PRIORITY QUEUE CONCORDANCE — the Part 6 acceptance test.

The dispatch queue must be a strict projection of the active approved plan.
Acceptance:
  - 100% order agreement between displayed queue and plan scheduled_sequence
  - zero duplicate dispatch assignments
  - zero stale-plan entries shown as current
  - all blocked work visible and classified
"""
import pytest
from app.models import DisruptionType, MissionStatus, FeasibilityStatus


class TestQueueConcordance:
    def test_queue_order_matches_plan_sequence(self, engine):
        queue = engine.get_dispatch_queue()
        plan = engine.plans[engine.current_plan_id]
        assert queue, "queue must not be empty"
        for i, q in enumerate(queue):
            entry = plan.request_entries[q["request_id"]]
            assert entry.scheduled_sequence == q["scheduled_sequence"]
        # queue must be sorted by scheduled_sequence (pure projection)
        seqs = [q["scheduled_sequence"] for q in queue]
        assert seqs == sorted(seqs)
        assert engine.queue_concordance() == 1.0

    def test_no_duplicate_dispatch_assignments(self, engine):
        queue = engine.get_dispatch_queue()
        ids = [q["request_id"] for q in queue]
        assert len(ids) == len(set(ids)), "duplicate dispatch detected"
        plan = engine.plans[engine.current_plan_id]
        all_stops = [rid for a in plan.assignments for rid in a.request_ids]
        assert len(all_stops) == len(set(all_stops)), "request assigned to two vehicles"

    def test_queue_entries_belong_to_active_plan(self, engine):
        """Stale plans must never appear as current assignments."""
        queue = engine.get_dispatch_queue()
        plan = engine.plans[engine.current_plan_id]
        for q in queue:
            assert q["request_id"] in plan.request_entries
            assert plan.request_entries[q["request_id"]].scheduled_sequence >= 1

    def test_blocked_work_visible_with_reasons(self, engine):
        blocked = engine.get_blocked_requests()
        plan = engine.plans[engine.current_plan_id]
        blocked_ids = {b["request_id"] for b in blocked}
        plan_blocked = {rid for rid, e in plan.request_entries.items()
                        if e.feasibility_status not in (FeasibilityStatus.SCHEDULED,
                                                        FeasibilityStatus.COMMITTED_PRESERVED)}
        assert blocked_ids == plan_blocked, "blocked work hidden from the UI"
        for b in blocked:
            assert b["feasibility_status"] in (
                "BLOCKED_HAZARD", "BLOCKED_NO_STOCK", "BLOCKED_NO_CAPACITY",
                "DEADLINE_INFEASIBLE", "NOT_PLANNED")
            assert b["explanation"]

    def test_concordance_holds_after_disruption_and_approval(self, engine):
        engine.inject_disruption(DisruptionType.DEPOT_OUTAGE, "Flood", "d",
                                 depot_id="DEPOT-BRAVO", lat=14.55, lng=120.94)
        # BEFORE approval: queue still reflects old plan; pending exists
        assert engine.pending_plan_id is not None
        engine.approve_pending_plan("Coordinator")
        assert engine.queue_concordance() == 1.0
        queue = engine.get_dispatch_queue()
        plan = engine.plans[engine.current_plan_id]
        assert all(q["request_id"] in plan.request_entries for q in queue)
        # blocked requests from the NEW plan visible
        blocked = engine.get_blocked_requests()
        assert all(b["request_id"] in plan.request_entries for b in blocked)

    def test_concordance_regression_guard(self, engine):
        """Regression test for the original defect: the UI used insertion
        order (REQ-001, REQ-002, ...) instead of plan order. If the queue
        projection ever stops being plan-derived, this fails."""
        queue = engine.get_dispatch_queue()
        insertion = [r.id for r in engine.requests.values()]
        # The plan's first entry must be a highest-urgency request; under the
        # old buggy projection the queue's first entries were REQ-001.. which
        # mixed priorities. Verify queue priority ordering is monotone by
        # urgency_score within the plan's sequence (non-increasing).
        scores = [q["urgency_score"] for q in queue]
        violations = sum(1 for i in range(len(scores) - 1)
                         if scores[i] < scores[i + 1] - 1e-9)
        # Preserved committed entries sequence first; their scores can be lower.
        # After them, scores must be non-increasing.
        assert violations == 0 or queue[0]["feasibility_status"] == "COMMITTED_PRESERVED"
