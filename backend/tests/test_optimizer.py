"""Optimizer correctness: feasibility guarantees, priority ordering,
determinism, 2-opt behavior, deadline flags, preservation, blocked reasons."""
import pytest
from app.models import (AidRequest, AidItem, Location, Depot, Vehicle, PriorityLevel,
                        MissionStatus, FeasibilityStatus)
from app.optimizer import OptimizerEngine, urgency_score, request_sort_key, haversine_distance_km


def make_depot(inv=None):
    return Depot(id="D1", name="Depot", location=Location(id="L1", name="d", lat=0.0, lng=0.0),
                 inventory=inv or {"potable_water_liters": 1000.0, "trauma_kits": 100.0})


def make_vehicle(cap=5000.0, speed=60.0, depot="D1"):
    return Vehicle(id="V1", name="Truck", vehicle_type="Heavy 4x4 Cargo", capacity_kg=cap,
                   base_depot_id=depot, current_lat=0.0, current_lng=0.0, speed_kmh=speed)


def make_request(rid, lat, lng, qty=50.0, prio=PriorityLevel.MEDIUM, deadline=24.0,
                 item="potable_water_liters", people=50):
    return AidRequest(id=rid, requester_name="t",
                      location=Location(id=f"l{rid}", name="s", lat=lat, lng=lng),
                      items=[AidItem(item_type=item, quantity=qty, unit="units")],
                      priority=prio, deadline_hours=deadline, affected_people=people)


class TestFeasibility:
    def test_inventory_never_exceeded(self):
        eng = OptimizerEngine()
        dep = make_depot({"potable_water_liters": 100.0})  # only 100 L
        reqs = [make_request(f"R{i}", 0.01 * i, 0.01 * i, qty=50.0) for i in range(8)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()], version_label="t")
        scheduled = [e for e in plan.request_entries.values()
                     if e.feasibility_status == FeasibilityStatus.SCHEDULED]
        consumed = sum(r.items[0].quantity for r in reqs
                        if r.id in {e.request_id for e in scheduled})
        assert consumed <= 100.0
        # remaining requests must be blocked with a stock reason
        blocked = [e for e in plan.request_entries.values()
                   if e.feasibility_status == FeasibilityStatus.BLOCKED_NO_STOCK]
        assert len(blocked) >= 6  # 100 L -> exactly 2 requests servable

    def test_capacity_never_exceeded(self):
        eng = OptimizerEngine()
        dep = make_depot({"potable_water_liters": 1000.0, "trauma_kits": 100.0,
                          "generators": 300.0})  # stock never binds; capacity binds
        # each request = 100 generators x 45 kg = 4500 kg; capacity 5000
        reqs = [make_request(f"R{i}", 0.01 * i, 0.01 * i, qty=100.0, item="generators")
                for i in range(3)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle(cap=5000.0)],
                                    version_label="t")
        scheduled = [e for e in plan.request_entries.values()
                     if e.feasibility_status == FeasibilityStatus.SCHEDULED]
        assert len(scheduled) == 1  # 4500 fits, 9000 exceeds capacity
        assert any(e.feasibility_status == FeasibilityStatus.BLOCKED_NO_CAPACITY
                   for e in plan.request_entries.values())

    def test_hazard_zone_blocks_requests(self):
        eng = OptimizerEngine()
        dep = make_depot()
        reqs = [make_request("R1", 0.05, 0.05), make_request("R2", 0.5, 0.5)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                   blocked_locations=[(0.05, 0.05, 3.5)], version_label="t")
        assert plan.request_entries["R1"].feasibility_status == FeasibilityStatus.BLOCKED_HAZARD
        assert plan.request_entries["R2"].feasibility_status == FeasibilityStatus.SCHEDULED

    def test_every_request_has_an_entry(self):
        """Coverage guarantee: scheduled, preserved, or blocked-with-reason."""
        eng = OptimizerEngine()
        dep = make_depot({"potable_water_liters": 10.0})
        reqs = [make_request(f"R{i}", 0.01 * i, 0.0) for i in range(5)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                   version_label="t")
        assert set(plan.request_entries.keys()) == {r.id for r in reqs}

    def test_blocked_entries_carry_unmet_demand(self):
        eng = OptimizerEngine()
        dep = make_depot({"potable_water_liters": 0.0})
        reqs = [make_request("R1", 0.01, 0.01, qty=77.0)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                    version_label="t")
        entry = plan.request_entries["R1"]
        assert entry.feasibility_status == FeasibilityStatus.BLOCKED_NO_STOCK
        assert entry.unmet_demand == {"potable_water_liters": 77.0}
        assert entry.explanation_reference


class TestPriorityAndOrder:
    def test_critical_scheduled_before_low_in_sequence(self):
        eng = OptimizerEngine()
        dep = make_depot()
        reqs = [
            make_request("LOW1", 0.02, 0.02, prio=PriorityLevel.LOW),
            make_request("CRIT1", 0.03, 0.03, prio=PriorityLevel.CRITICAL),
            make_request("LOW2", 0.01, 0.01, prio=PriorityLevel.LOW),
        ]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                    version_label="t")
        crit = plan.request_entries["CRIT1"].scheduled_sequence
        assert crit < plan.request_entries["LOW1"].scheduled_sequence
        assert crit < plan.request_entries["LOW2"].scheduled_sequence

    def test_sequences_unique_and_contiguous(self):
        eng = OptimizerEngine()
        dep = make_depot()
        reqs = [make_request(f"R{i}", 0.01 * i, 0.0, prio=PriorityLevel.MEDIUM) for i in range(10)]
        plan = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                    version_label="t")
        seqs = sorted(e.scheduled_sequence for e in plan.request_entries.values()
                      if e.feasibility_status == FeasibilityStatus.SCHEDULED)
        assert seqs == list(range(1, len(seqs) + 1))

    def test_deterministic_tiebreaks(self):
        eng = OptimizerEngine()
        dep = make_depot()
        vehs = [make_vehicle(), Vehicle(id="V2", name="T2", vehicle_type="Heavy 4x4 Cargo",
                                        capacity_kg=5000.0, base_depot_id="D1",
                                        current_lat=0.0, current_lng=0.0, speed_kmh=60.0)]
        reqs = [make_request(f"R{i}", 0.01 * i, 0.0) for i in range(6)]
        p1 = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=vehs, version_label="a")
        p2 = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=vehs, version_label="b")
        assert [(a.vehicle_id, a.request_ids) for a in p1.assignments] == \
               [(a.vehicle_id, a.request_ids) for a in p2.assignments]

    def test_two_opt_improves_distance_and_preserves_priority_order(self):
        import random
        eng = OptimizerEngine()
        dep = make_depot()
        rng = random.Random(7)
        reqs = [make_request(f"R{i}", rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1),
                             prio=PriorityLevel.MEDIUM) for i in range(12)]
        no2opt = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                      version_label="x", apply_two_opt=False)
        with2opt = eng.solve_allocation(requests=reqs, depots=[dep], vehicles=[make_vehicle()],
                                        version_label="y", apply_two_opt=True)
        assert with2opt.total_distance_km <= no2opt.total_distance_km
        # 2-opt must never move a higher-priority stop after a lower one:
        hi = make_request("HI", 0.09, 0.09, prio=PriorityLevel.CRITICAL)
        lo = make_request("LO", 0.01, 0.01, prio=PriorityLevel.LOW)
        plan = eng.solve_allocation(requests=[hi, lo], depots=[dep], vehicles=[make_vehicle()],
                                    version_label="z")
        # find route order
        for a in plan.assignments:
            if "HI" in a.request_ids and "LO" in a.request_ids:
                assert a.request_ids.index("HI") < a.request_ids.index("LO")


class TestDeadlinesAndPreservation:
    def test_deadline_infeasibility_flagged(self):
        eng = OptimizerEngine()
        dep = make_depot()
        far = make_request("FAR", 0.5, 0.5, deadline=0.01)  # 0.6 min deadline, ~55 min drive
        plan = eng.solve_allocation(requests=[far], depots=[dep], vehicles=[make_vehicle()],
                                    version_label="t")
        assert "WARNING" in plan.request_entries["FAR"].explanation_reference

    def test_preserved_requests_keep_assignment_and_immutable_status(self):
        eng = OptimizerEngine()
        dep = make_depot()
        r = make_request("KEEP", 0.02, 0.02)
        r.status = MissionStatus.DISPATCHED
        r.assigned_vehicle_id = "V1"
        r.assigned_depot_id = "D1"
        others = [make_request(f"R{i}", 0.01 * i, 0.0) for i in range(3)]
        plan = eng.solve_allocation(requests=[r] + others, depots=[dep], vehicles=[make_vehicle()],
                                    preserve_request_ids=["KEEP"],
                                    committed_assignments={"KEEP": ("V1", "D1")},
                                    version_label="t")
        entry = plan.request_entries["KEEP"]
        assert entry.feasibility_status == FeasibilityStatus.COMMITTED_PRESERVED
        assert entry.assigned_vehicle == "V1"
        assert entry.assigned_depot == "D1"
        assert entry.scheduled_sequence >= 1  # sequenced, not dropped


class TestUrgencyScore:
    def test_score_ordering_across_priorities(self):
        crit = make_request("c", 0, 0, prio=PriorityLevel.CRITICAL, people=1)
        low = make_request("l", 0, 0, prio=PriorityLevel.LOW, people=300)
        assert urgency_score(crit) > urgency_score(low)

    def test_affected_people_tiebreak_within_class(self):
        a = make_request("a", 0, 0, prio=PriorityLevel.HIGH, people=10)
        b = make_request("b", 0, 0, prio=PriorityLevel.HIGH, people=200)
        assert urgency_score(b) > urgency_score(a)
