"""Phase II Milestone 6: optimizer correctness proofs.

A. EXACT ORACLE: for tiny scenarios (≤7 requests, 1 vehicle) brute-force ALL
   insertion orders and compare against the heuristic's route distance. The
   heuristic's result must be feasible and its distance within a documented
   factor of the exact optimum (never CLAIMED optimal — the gap is measured).

B. METAMORPHIC PROPERTIES: input transformations with provable output effects.

C. FEASIBILITY CHECKER: an independent verifier that re-checks every accepted
   plan against inventory, capacity and hazards from raw inputs.
"""
import itertools
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import (AidRequest, AidItem, Location, Depot, Vehicle, PriorityLevel,
                        MissionStatus, FeasibilityStatus)
from app.optimizer import OptimizerEngine, haversine_distance_km, request_sort_key


def mk_depot(inv=None, lat=0.0, lng=0.0):
    return Depot(id="D1", name="Depot", location=Location(id="L", name="d", lat=lat, lng=lng),
                 inventory=inv or {"potable_water_liters": 100000.0, "trauma_kits": 1000.0})


def mk_vehicle(cap=100000.0, speed=60.0):
    return Vehicle(id="V1", name="Truck", vehicle_type="Heavy 4x4 Cargo", capacity_kg=cap,
                  base_depot_id="D1", current_lat=0.0, current_lng=0.0, speed_kmh=speed)


def mk_req(rid, lat, lng, qty=10.0, prio=PriorityLevel.MEDIUM, people=50, deadline=24.0):
    return AidRequest(id=rid, requester_name="t",
                      location=Location(id=f"l{rid}", name="s", lat=lat, lng=lng),
                      items=[AidItem(item_type="potable_water_liters", quantity=qty, unit="u")],
                      priority=prio, deadline_hours=deadline, affected_people=people)


# ----------------------------------------------------------------------
# A. Exact oracle (small instances)
# ----------------------------------------------------------------------
class TestExactOracle:
    def route_km(self, depot, order):
        pts = [(depot.location.lat, depot.location.lng)] + \
              [(r.location.lat, r.location.lng) for r in order] + \
              [(depot.location.lat, depot.location.lng)]
        return sum(haversine_distance_km(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                   for i in range(len(pts) - 1))

    def test_heuristic_within_documented_gap_of_exact_optimum(self):
        """For 6 same-priority requests the heuristic (insertion + 2-opt)
        must land within 25% of the brute-force optimum on this instance,
        and ALWAYS feasible. This measures the optimality gap honestly —
        the heuristic is never claimed optimal."""
        import random
        eng = OptimizerEngine()
        rng = random.Random(123)
        reqs = [mk_req(f"R{i}", rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05))
                for i in range(6)]
        depot = mk_depot()
        plan = eng.solve_allocation(requests=reqs, depots=[depot],
                                   vehicles=[mk_vehicle()], version_label="t")
        sched = [e for e in plan.request_entries.values()
                 if e.feasibility_status == FeasibilityStatus.SCHEDULED]
        assert len(sched) == 6  # feasible: everything fits
        by_id = {r.id: r for r in reqs}
        order = [by_id[e.request_id] for e in
                 sorted(sched, key=lambda e: e.scheduled_sequence)]
        heuristic_km = self.route_km(depot, order)
        exact_km = min(self.route_km(depot, list(p)) for p in itertools.permutations(reqs))
        gap = (heuristic_km - exact_km) / exact_km
        assert gap <= 0.25, f"optimality gap {gap:.1%} exceeds documented bound"
        assert heuristic_km >= exact_km  # sanity: optimum is a lower bound

    def test_optimum_lower_bound_property(self):
        """The heuristic's distance can never beat the exact optimum."""
        import random
        eng = OptimizerEngine()
        rng = random.Random(7)
        reqs = [mk_req(f"R{i}", rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03))
                for i in range(5)]
        depot = mk_depot()
        plan = eng.solve_allocation(requests=reqs, depots=[depot],
                                    vehicles=[mk_vehicle()], version_label="t")
        by_id = {r.id: r for r in reqs}
        sched = sorted([e for e in plan.request_entries.values()
                        if e.feasibility_status == FeasibilityStatus.SCHEDULED],
                       key=lambda e: e.scheduled_sequence)
        order = [by_id[e.request_id] for e in sched]
        heuristic_km = self.route_km(depot, order)
        exact_km = min(self.route_km(depot, list(p)) for p in itertools.permutations(reqs))
        assert heuristic_km >= exact_km - 1e-9


# ----------------------------------------------------------------------
# B. Metamorphic properties
# ----------------------------------------------------------------------
class TestMetamorphic:
    def test_more_inventory_never_reduces_feasibility(self):
        """Increasing stock cannot invalidate a feasible solution."""
        eng = OptimizerEngine()
        reqs = [mk_req(f"R{i}", 0.01 * i, 0.0, qty=50.0) for i in range(4)]
        poor = mk_depot({"potable_water_liters": 100.0})
        rich = mk_depot({"potable_water_liters": 10000.0})
        p_poor = eng.solve_allocation(requests=reqs, depots=[poor], vehicles=[mk_vehicle()], version_label="a")
        p_rich = eng.solve_allocation(requests=reqs, depots=[rich], vehicles=[mk_vehicle()], version_label="b")
        sched_poor = sum(1 for e in p_poor.request_entries.values() if e.feasibility_status == FeasibilityStatus.SCHEDULED)
        sched_rich = sum(1 for e in p_rich.request_entries.values() if e.feasibility_status == FeasibilityStatus.SCHEDULED)
        assert sched_rich >= sched_poor

    def test_removing_hazard_never_blocks_more_requests(self):
        """Removing a hazard zone cannot make MORE requests blocked."""
        eng = OptimizerEngine()
        reqs = [mk_req(f"R{i}", 0.02 * i, 0.02 * i) for i in range(5)]
        depot = mk_depot()
        with_hazard = eng.solve_allocation(requests=reqs, depots=[depot], vehicles=[mk_vehicle()],
                                           blocked_locations=[(0.04, 0.04, 3.0)], version_label="a")
        no_hazard = eng.solve_allocation(requests=reqs, depots=[depot], vehicles=[mk_vehicle()],
                                         version_label="b")
        blocked_with = sum(1 for e in with_hazard.request_entries.values()
                            if e.feasibility_status == FeasibilityStatus.BLOCKED_HAZARD)
        blocked_without = sum(1 for e in no_hazard.request_entries.values()
                              if e.feasibility_status == FeasibilityStatus.BLOCKED_HAZARD)
        assert blocked_without <= blocked_with

    def test_blocked_depot_is_never_allocated_from(self):
        eng = OptimizerEngine()
        d1 = mk_depot({"potable_water_liters": 100000.0})
        d2 = Depot(id="D2", name="Blocked", location=Location(id="L2", name="d", lat=5.0, lng=5.0),
                   inventory={"potable_water_liters": 100000.0})
        reqs = [mk_req("R1", 5.0, 5.0)]  # right next to the blocked depot
        v2 = Vehicle(id="V2", name="T2", vehicle_type="Heavy 4x4 Cargo", capacity_kg=100000.0,
                     base_depot_id="D2", current_lat=5.0, current_lng=5.0, speed_kmh=60.0)
        plan = eng.solve_allocation(requests=reqs, depots=[d1, d2], vehicles=[mk_vehicle(), v2],
                                   blocked_depot_ids=["D2"], version_label="t")
        entry = plan.request_entries["R1"]
        if entry.feasibility_status == FeasibilityStatus.SCHEDULED:
            assert entry.assigned_depot != "D2"  # never from the blocked depot
            assert entry.assigned_vehicle != "V2"

    def test_completed_delivery_cannot_become_uncompleted_via_replan(self):
        eng = OptimizerEngine()
        reqs = [mk_req(f"R{i}", 0.01 * i, 0.0) for i in range(3)]
        depot = mk_depot()
        base = eng.solve_allocation(requests=reqs, depots=[depot], vehicles=[mk_vehicle()],
                                    version_label="v1")
        # mark R0 delivered (committed)
        reqs[0].status = MissionStatus.DELIVERED
        reqs[0].is_delivered = True
        reqs[0].assigned_vehicle_id = "V1"
        reqs[0].assigned_depot_id = "D1"
        replan = eng.solve_allocation(requests=reqs, depots=[depot], vehicles=[mk_vehicle()],
                                      preserve_request_ids=["R0"],
                                      committed_assignments={"R0": ("V1", "D1")},
                                      version_label="v2")
        assert replan.request_entries["R0"].feasibility_status == FeasibilityStatus.COMMITTED_PRESERVED
        assert reqs[0].is_delivered is True  # state untouched

    def test_identical_seeds_identical_outputs(self):
        from app.benchmark import BenchmarkScenario, plan_optimizer
        sc1 = BenchmarkScenario(seed=99, n_requests=40)
        sc2 = BenchmarkScenario(seed=99, n_requests=40)
        r1, _ = plan_optimizer(sc1)
        r2, _ = plan_optimizer(sc2)
        assert {k: v for k, v in r1.items()} == {k: v for k, v in r2.items()}

    def test_changed_inputs_reflected_in_outputs(self):
        """A request added to the scenario must appear in the plan (scheduled
        or blocked) — the plan cannot silently ignore new input."""
        eng = OptimizerEngine()
        depot = mk_depot()
        base_reqs = [mk_req(f"R{i}", 0.01 * i, 0.0) for i in range(3)]
        p1 = eng.solve_allocation(requests=base_reqs, depots=[depot], vehicles=[mk_vehicle()], version_label="a")
        extra = mk_req("NEW", 0.5, 0.5)
        p2 = eng.solve_allocation(requests=base_reqs + [extra], depots=[depot],
                                  vehicles=[mk_vehicle()], version_label="b")
        assert "NEW" in p2.request_entries
        assert "NEW" not in p1.request_entries


# ----------------------------------------------------------------------
# C. Independent feasibility verifier
# ----------------------------------------------------------------------
def verify_plan_feasibility(plan, requests, depots, vehicles, blocked_locations=None):
    """Independent re-check of every accepted assignment from RAW inputs.
    Returns a list of violations (empty = feasible)."""
    violations = []
    req_by_id = {r.id: r for r in requests}
    depot_by_id = {d.id: d for d in depots}
    veh_by_id = {v.id: v for v in vehicles}
    # simulated stock consumption
    stock = {d.id: dict(d.inventory) for d in depots}
    loads = {v.id: 0.0 for v in vehicles}
    blocked_locations = blocked_locations or []

    for asgn in plan.assignments:
        v = veh_by_id.get(asgn.vehicle_id)
        if v is None:
            violations.append(f"unknown vehicle {asgn.vehicle_id}")
            continue
        for rid in asgn.request_ids:
            r = req_by_id.get(rid)
            if r is None:
                violations.append(f"unknown request {rid}")
                continue
            w = sum(i.quantity * {"potable_water_liters": 1.0, "trauma_kits": 4.5,
                                  "rations_mre": 0.8, "hygiene_kits": 2.0,
                                  "generators": 45.0}.get(i.item_type, 1.5)
                    for i in r.items)
            loads[v.id] += max(w, 5.0)
            if loads[v.id] > v.capacity_kg:
                violations.append(f"capacity exceeded on {v.id} at {rid}")
            for item in r.items:
                avail = stock[asgn.depot_id].get(item.item_type, 0.0)
                if avail < item.quantity:
                    violations.append(f"insufficient stock at {asgn.depot_id} for {rid}")
                stock[asgn.depot_id][item.item_type] = avail - item.quantity
            for b_lat, b_lng, b_rad in blocked_locations:
                if haversine_distance_km(r.location.lat, r.location.lng, b_lat, b_lng) <= b_rad:
                    violations.append(f"{rid} scheduled inside hazard zone")
    return violations


class TestIndependentFeasibility:
    def test_seed_scenario_plan_is_feasible_under_independent_verifier(self):
        from app.state_engine import CrisisStateEngine
        eng = CrisisStateEngine(seed=42, org_id="ORG-PACIFIC", persist=False)
        plan = eng.plans[eng.current_plan_id]
        violations = verify_plan_feasibility(
            plan, list(eng.requests.values()), list(eng.depots.values()),
            list(eng.vehicles.values()))
        assert violations == []

    def test_recovered_plan_is_feasible_under_independent_verifier(self):
        from app.state_engine import CrisisStateEngine
        from app.models import DisruptionType
        eng = CrisisStateEngine(seed=42, org_id="ORG-PACIFIC", persist=False)
        eng.inject_disruption(DisruptionType.DEPOT_OUTAGE, "Flood", "d",
                              depot_id="DEPOT-BRAVO", lat=14.55, lng=120.94)
        eng.approve_pending_plan("C")
        plan = eng.plans[eng.current_plan_id]
        violations = verify_plan_feasibility(
            plan, list(eng.requests.values()), list(eng.depots.values()),
            list(eng.vehicles.values()),
            blocked_locations=[(14.55, 120.94, 3.5)])
        assert violations == []
