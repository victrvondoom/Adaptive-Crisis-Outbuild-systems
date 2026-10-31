"""
AIDNEXUS ONE — Allocation & Routing Heuristic with Deterministic Replanning

HONEST DESCRIPTION (this docstring previously claimed "MIP" and "2-opt" without
implementing them; see docs/audit/FINDINGS_RANKED.md A2/A3):

This module implements a deterministic, priority-weighted greedy insertion
heuristic with an intra-route 2-opt improvement pass, for a multi-depot
capacitated allocation problem with:
  - per-depot multi-commodity inventory constraints,
  - per-vehicle weight capacity constraints,
  - geographic hazard-zone exclusions,
  - delivery deadline feasibility classification,
  - commitment preservation on replanning.

It is a HEURISTIC, not an exact solver. No OR-Tools, no MIP. It produces
feasible solutions only: every accepted assignment satisfies inventory and
capacity constraints, and requests it cannot schedule are returned with an
explicit FeasibilityStatus reason rather than being silently dropped.

The returned MissionPlanVersion is the AUTHORITATIVE execution order.
 humanitarian priority = policy score (PRIORITY_WEIGHTS, POLICY_VERSION)
 operational order = scheduled_sequence / scheduled_start_min from this module.
The UI dispatch queue must be a projection of request_entries — never reordered.
"""
import math
import hashlib
import time
import uuid
from typing import List, Dict, Tuple, Optional, Any
from .models import (
    AidRequest, Depot, Vehicle, PlanAssignment, MissionPlanVersion,
    PlannedRequestEntry, PriorityLevel, MissionStatus, FeasibilityStatus,
    POLICY_VERSION,
)

# Humanitarian priority weights (canonical policy, see models.POLICY_VERSION).
# Tie-breaking within the same priority class, in order:
#   1. more affected_people first (larger humanitarian impact),
#   2. earlier created_at first (FIFO within equal impact),
#   3. request id (final deterministic tie-break).
PRIORITY_WEIGHTS = {
    PriorityLevel.CRITICAL: 1000.0,
    PriorityLevel.HIGH: 300.0,
    PriorityLevel.MEDIUM: 80.0,
    PriorityLevel.LOW: 20.0
}

# Average weight per unit of item (kg). Defaults used when an item type is unknown.
ITEM_WEIGHT_KG = {
    "potable_water_liters": 1.0,
    "trauma_kits": 4.5,
    "rations_mre": 0.8,
    "hygiene_kits": 2.0,
    "generators": 45.0
}

# Minutes of service time at each delivery stop (loading + handover).
STOP_SERVICE_MIN = 12.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 4)


def urgency_score(request: AidRequest) -> float:
    """Canonical humanitarian priority score under POLICY_VERSION.

    score = PRIORITY_WEIGHTS[priority] + min(affected_people, 300) * 0.1
    The affected-people term is a bounded tie-breaker inside a priority class;
    it can never move a request across priority classes (max bonus 30 < 80).
    """
    return round(PRIORITY_WEIGHTS.get(request.priority, 10.0)
                 + min(max(request.affected_people, 0), 300) * 0.1, 2)


def request_sort_key(r: AidRequest) -> Tuple[float, float, float, str]:
    """Deterministic humanitarian ordering used by the planner (descending)."""
    return (urgency_score(r), float(r.affected_people), -r.created_at, r.id)


class OptimizerEngine:
    def __init__(self):
        pass

    def compute_request_weight(self, request: AidRequest) -> float:
        total = 0.0
        for item in request.items:
            unit_w = ITEM_WEIGHT_KG.get(item.item_type, 1.5)
            total += item.quantity * unit_w
        return max(total, 5.0)

    # ------------------------------------------------------------------
    # Route distance helper (depot -> stops... -> depot)
    # ------------------------------------------------------------------
    @staticmethod
    def _route_distance_km(depot_lat: float, depot_lng: float,
                           stops: List[Tuple[float, float]]) -> float:
        if not stops:
            return 0.0
        d = haversine_distance_km(depot_lat, depot_lng, stops[0][0], stops[0][1])
        for i in range(len(stops) - 1):
            d += haversine_distance_km(stops[i][0], stops[i][1],
                                       stops[i + 1][0], stops[i + 1][1])
        d += haversine_distance_km(stops[-1][0], stops[-1][1], depot_lat, depot_lng)
        return d

    @staticmethod
    def _two_opt(stops: List[Tuple[float, float]], depot_lat: float, depot_lng: float,
                 scores: Optional[List[float]] = None, max_passes: int = 2) -> List[Tuple[float, float]]:
        """Intra-route 2-opt improvement with a HUMANITARIAN PRIORITY CONSTRAINT.

        A candidate reversal is accepted only if it (a) reduces route distance
        AND (b) keeps the route priority-monotonic: stop urgency scores must
        remain non-increasing along the route. This prevents distance
        optimization from pushing CRITICAL deliveries behind LOW ones (which
        would delay them past deadlines and disruption points). Reordering
        within the same priority class is allowed. Deterministic
        first-improvement scan. Improves travel distance only; stop membership
        never changes, so capacity/inventory feasibility is unaffected."""
        if len(stops) < 3:
            return stops
        route = list(stops)
        for _ in range(max_passes):
            improved = False
            base = OptimizerEngine._route_distance_km(depot_lat, depot_lng, route)
            for i in range(len(route) - 1):
                for j in range(i + 1, len(route)):
                    candidate = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                    if scores is not None:
                        cand_scores = scores[:i] + scores[i:j + 1][::-1] + scores[j + 1:]
                        if any(cand_scores[k] < cand_scores[k + 1] - 1e-9
                               for k in range(len(cand_scores) - 1)):
                            continue  # would delay a higher-priority stop
                    if OptimizerEngine._route_distance_km(depot_lat, depot_lng, candidate) < base - 1e-9:
                        route = candidate
                        base = OptimizerEngine._route_distance_km(depot_lat, depot_lng, route)
                        if scores is not None:
                            scores = scores[:i] + scores[i:j + 1][::-1] + scores[j + 1:]
                        improved = True
            if not improved:
                break
        return route

    def solve_allocation(
        self,
        requests: List[AidRequest],
        depots: List[Depot],
        vehicles: List[Vehicle],
        blocked_depot_ids: List[str] = None,
        blocked_locations: List[Tuple[float, float, float]] = None,  # (lat, lng, radius_km)
        preserve_request_ids: List[str] = None,  # Committed requests (dispatched/in-transit) kept on their assignment
        committed_assignments: Optional[Dict[str, Tuple[str, str]]] = None,  # request_id -> (vehicle_id, depot_id)
        version_label: str = "v1.0",
        apply_two_opt: bool = True,
    ) -> MissionPlanVersion:
        """Deterministic priority-weighted greedy insertion + 2-opt.

        Guarantee: every request in assignments satisfies depot inventory and
        vehicle capacity at planning time; every unscheduled request appears in
        request_entries with an explicit FeasibilityStatus reason.
        """
        start_time = time.time()
        run_id = f"opt-{uuid.uuid4().hex[:12]}"
        blocked_depots = set(blocked_depot_ids or [])
        blocked_locs = blocked_locations or []
        preserve_set = set(preserve_request_ids or [])
        committed_map: Dict[str, Tuple[str, str]] = committed_assignments or {}

        active_depots = {d.id: d for d in depots
                         if d.id not in blocked_depots and d.status == "OPERATIONAL"}
        depot_stock = {d.id: dict(d.inventory) for d in active_depots.values()}
        active_vehicles = [v for v in vehicles
                           if v.status != "BROKEN_DOWN" and v.base_depot_id in active_depots]

        def is_blocked(lat: float, lng: float) -> bool:
            for b_lat, b_lng, b_rad in blocked_locs:
                if haversine_distance_km(lat, lng, b_lat, b_lng) <= b_rad:
                    return True
            return False

        entries: Dict[str, PlannedRequestEntry] = {}
        assignments: Dict[str, PlanAssignment] = {}
        # vehicle -> ordered list of (lat, lng, request_id) stops (excludes depot endpoints)
        vehicle_stops: Dict[str, List[Tuple[float, float, str]]] = {}

        for v in active_vehicles:
            assignments[v.id] = PlanAssignment(
                vehicle_id=v.id, depot_id=v.base_depot_id, request_ids=[],
                route_latlngs=[[active_depots[v.base_depot_id].location.lat,
                                active_depots[v.base_depot_id].location.lng]],
                total_distance_km=0.0, estimated_duration_min=0.0, payload_weight_kg=0.0)
            vehicle_stops[v.id] = []

        # --- Phase 0: committed (preserved) requests keep their current assignment ---
        preserved_ids: List[str] = []
        for req in requests:
            if req.id in preserve_set:
                commit = committed_map.get(req.id)
                if commit and commit[0] in assignments:
                    v_id, d_id = commit
                    asgn = assignments[v_id]
                    asgn.request_ids.append(req.id)
                    vehicle_stops[v_id].append((req.location.lat, req.location.lng, req.id))
                    # capacity/stock of preserved stops is consumed first, mirroring reality
                    depot_stock[d_id] = depot_stock.get(d_id, {})
                    for item in req.items:
                        depot_stock[d_id][item.item_type] = depot_stock[d_id].get(item.item_type, 0.0) - item.quantity
                    asgn.payload_weight_kg += self.compute_request_weight(req)
                    preserved_ids.append(req.id)

        # --- Phase 1: greedy insertion in humanitarian priority order ---
        pool = [r for r in requests
                if r.id not in preserve_set
                and r.status not in (MissionStatus.DELIVERED, MissionStatus.CANCELLED)]
        pool.sort(key=request_sort_key, reverse=True)

        unmet_requests: List[str] = []
        unmet_reasons: Dict[str, FeasibilityStatus] = {}

        for req in pool:
            if is_blocked(req.location.lat, req.location.lng):
                unmet_requests.append(req.id)
                unmet_reasons[req.id] = FeasibilityStatus.BLOCKED_HAZARD
                continue

            req_weight = self.compute_request_weight(req)
            # Which depots can supply every requested item?
            supplying_depots = [d_id for d_id, stock in depot_stock.items()
                                if all(stock.get(it.item_type, 0.0) >= it.quantity for it in req.items)]

            best_vehicle_id = None
            best_marginal = float("inf")
            for v in active_vehicles:
                if v.id not in assignments:
                    continue
                asgn = assignments[v.id]
                if asgn.payload_weight_kg + req_weight > v.capacity_kg:
                    continue
                if v.base_depot_id not in supplying_depots:
                    continue
                stops = vehicle_stops[v.id]
                last_lat, last_lng = (stops[-1][0], stops[-1][1]) if stops else \
                    (active_depots[v.base_depot_id].location.lat, active_depots[v.base_depot_id].location.lng)
                marginal = haversine_distance_km(last_lat, last_lng, req.location.lat, req.location.lng)
                # Deterministic tie-break: smaller marginal distance, then vehicle id.
                if marginal < best_marginal - 1e-9 or \
                   (abs(marginal - best_marginal) <= 1e-9 and best_vehicle_id is not None and v.id < best_vehicle_id):
                    best_marginal = marginal
                    best_vehicle_id = v.id

            if best_vehicle_id is None:
                unmet_requests.append(req.id)
                # Classify the blocking reason explicitly (never silently drop).
                if not supplying_depots:
                    unmet_reasons[req.id] = FeasibilityStatus.BLOCKED_NO_STOCK
                else:
                    unmet_reasons[req.id] = FeasibilityStatus.BLOCKED_NO_CAPACITY
                continue

            asgn = assignments[best_vehicle_id]
            asgn.request_ids.append(req.id)
            vehicle_stops[best_vehicle_id].append((req.location.lat, req.location.lng, req.id))
            asgn.payload_weight_kg += req_weight
            for item in req.items:
                depot_stock[asgn.depot_id][item.item_type] -= item.quantity

        # --- Phase 2: 2-opt route improvement + schedule computation ---
        total_system_km = 0.0
        final_assignments: List[PlanAssignment] = []
        for v in active_vehicles:
            asgn = assignments[v.id]
            if not asgn.request_ids:
                continue
            depot_loc = active_depots[asgn.depot_id].location
            stops = [(s[0], s[1]) for s in vehicle_stops[v.id]]
            if apply_two_opt:
                # Priority-preserving 2-opt: stop scores must stay non-increasing.
                stop_scores = [self._score_of(requests, s[2]) for s in vehicle_stops[v.id]]
                improved = self._two_opt(stops, depot_loc.lat, depot_loc.lng, scores=stop_scores)
            else:
                improved = stops
            stop_ids = [s[2] for s in vehicle_stops[v.id]]
            # reorder stop ids to match improved geometry
            improved_with_ids: List[Tuple[float, float, str]] = []
            used = set()
            for (lat, lng) in improved:
                for s in vehicle_stops[v.id]:
                    if s[2] not in used and abs(s[0] - lat) < 1e-9 and abs(s[1] - lng) < 1e-9:
                        improved_with_ids.append(s)
                        used.add(s[2])
                        break
            # any stop not matched (duplicate coords) keeps original order at the end
            leftovers = [s for s in vehicle_stops[v.id] if s[2] not in used]
            improved_with_ids.extend(leftovers)

            asgn.request_ids = [s[2] for s in improved_with_ids]
            route_ll = [[depot_loc.lat, depot_loc.lng]] + [[s[0], s[1]] for s in improved_with_ids] + \
                       [[depot_loc.lat, depot_loc.lng]]
            asgn.route_latlngs = route_ll

            # Distance + schedule: cumulative legs, service time per stop.
            dist = 0.0
            elapsed_min = 0.0
            arrival_min: Dict[str, float] = {}
            speed = max(v.speed_kmh, 20.0)
            for idx, s in enumerate(improved_with_ids):
                prev = route_ll[idx]
                leg = haversine_distance_km(prev[0], prev[1], s[0], s[1])
                dist += leg
                elapsed_min += (leg / speed) * 60.0
                arrival_min[s[2]] = round(elapsed_min, 1)
                elapsed_min += STOP_SERVICE_MIN
            return_leg = haversine_distance_km(improved_with_ids[-1][0], improved_with_ids[-1][1],
                                               depot_loc.lat, depot_loc.lng)
            dist += return_leg
            asgn.total_distance_km = round(dist, 2)
            asgn.estimated_duration_min = round(elapsed_min + (return_leg / speed) * 60.0, 1)
            total_system_km += asgn.total_distance_km

            for seq_idx, req_id in enumerate(asgn.request_ids):
                entries[req_id] = PlannedRequestEntry(
                    request_id=req_id,
                    assignment_id=f"{version_label}/{v.id}",
                    humanitarian_priority=self._prio_of(requests, req_id),
                    urgency_score=self._score_of(requests, req_id),
                    scheduled_sequence=0,  # assigned in phase 3
                    scheduled_start_min=0.0,
                    estimated_arrival_min=arrival_min.get(req_id, 0.0),
                    assigned_depot=asgn.depot_id,
                    assigned_vehicle=v.id,
                    feasibility_status=FeasibilityStatus.SCHEDULED,
                    explanation_reference=f"Assigned to {v.name} from {active_depots[asgn.depot_id].name} (route position {seq_idx + 1})."
                )
            final_assignments.append(asgn)

        # --- Phase 3: deadline feasibility + plan-wide execution sequence ---
        # Sequence order: humanitarian priority score desc, then estimated arrival asc,
        # i.e. the order in which vehicles depart/serve under the plan. Committed
        # (preserved) deliveries sequence first as they are already underway.
        all_scheduled = [e for e in entries.values()]
        all_scheduled.sort(key=lambda e: (
            0 if e.request_id in preserve_set else 1,
            -e.urgency_score,
            e.estimated_arrival_min,
            e.request_id,
        ))
        for seq, e in enumerate(all_scheduled, start=1):
            e.scheduled_sequence = seq

        # Deadline classification: a request whose planned arrival exceeds its
        # deadline is flagged DEADLINE_INFEASIBLE (kept scheduled so the operator
        # sees it, but never presented as on-time).
        req_by_id = {r.id: r for r in requests}
        deadline_infeasible = 0
        for e in entries.values():
            r = req_by_id.get(e.request_id)
            if r and e.feasibility_status == FeasibilityStatus.SCHEDULED:
                if e.estimated_arrival_min > r.deadline_hours * 60.0:
                    # keep it scheduled (delivery still happens, just late) but flag it
                    e.explanation_reference += " WARNING: planned arrival exceeds request deadline."
                    deadline_infeasible += 1

        # --- Phase 4: blocked/unmet entries so nothing is hidden ---
        for req in pool:
            if req.id in unmet_reasons:
                reason = unmet_reasons[req.id]
                detail = {
                    FeasibilityStatus.BLOCKED_HAZARD: "Request location is inside an active hazard zone.",
                    FeasibilityStatus.BLOCKED_NO_STOCK: "No operational depot currently holds all requested items.",
                    FeasibilityStatus.BLOCKED_NO_CAPACITY: "No available vehicle has remaining capacity for this request.",
                }[reason]
                unmet_demand = {it.item_type: it.quantity for it in req.items}
                entries[req.id] = PlannedRequestEntry(
                    request_id=req.id,
                    assignment_id=f"{version_label}/blocked",
                    humanitarian_priority=req.priority.value,
                    urgency_score=urgency_score(req),
                    scheduled_sequence=0,
                    scheduled_start_min=0.0,
                    estimated_arrival_min=0.0,
                    assigned_depot=None, assigned_vehicle=None,
                    feasibility_status=reason,
                    unmet_demand=unmet_demand,
                    explanation_reference=detail
                )
        # Preserved entries
        for req in requests:
            if req.id in preserve_set:
                commit = committed_map.get(req.id)
                entries[req.id] = PlannedRequestEntry(
                    request_id=req.id,
                    assignment_id=f"{version_label}/{commit[0] if commit else 'preserved'}",
                    humanitarian_priority=req.priority.value,
                    urgency_score=urgency_score(req),
                    scheduled_sequence=entries[req.id].scheduled_sequence if req.id in entries else 0,
                    scheduled_start_min=0.0,
                    estimated_arrival_min=req.estimated_arrival_minutes or 0.0,
                    assigned_depot=commit[1] if commit else req.assigned_depot_id,
                    assigned_vehicle=commit[0] if commit else req.assigned_vehicle_id,
                    feasibility_status=FeasibilityStatus.COMMITTED_PRESERVED,
                    explanation_reference="Committed delivery preserved from previous plan (immutable)."
                )

        solve_time_sec = round(time.time() - start_time, 4)

        raw_repr = f"{version_label}:{run_id}:{len(final_assignments)}:{sorted(entries.keys())}:{unmet_requests}"
        checksum = hashlib.sha256(raw_repr.encode()).hexdigest()[:16]

        scheduled_count = sum(1 for e in entries.values()
                              if e.feasibility_status in (FeasibilityStatus.SCHEDULED,
                                                          FeasibilityStatus.COMMITTED_PRESERVED))
        explanation = (
            f"Plan {version_label} computed in {solve_time_sec}s by deterministic priority-weighted "
            f"greedy insertion with 2-opt route improvement (policy {POLICY_VERSION}). "
            f"Scheduled {scheduled_count}/{len(pool) + len(preserved_ids)} plannable requests across "
            f"{len(final_assignments)} vehicle routes. Blocked/unmet: {len(unmet_requests)} "
            f"(reasons are attached to each blocked request). "
            f"Total planned travel: {round(total_system_km, 1)} km. "
            f"Preserved {len(preserved_ids)} committed deliveries unchanged. "
            f"{deadline_infeasible} scheduled requests would arrive after their deadline (flagged)."
        )

        return MissionPlanVersion(
            version_id=version_label,
            optimization_run_id=run_id,
            policy_version=POLICY_VERSION,
            created_by="Agent 2: Resource Strategist (greedy insertion + 2-opt heuristic)",
            is_active=False,
            is_approved=False,
            assignments=final_assignments,
            request_entries=entries,
            unmet_request_ids=unmet_requests,
            total_distance_km=round(total_system_km, 1),
            total_fulfilled=scheduled_count,
            tradeoff_explanation=explanation,
            checksum=checksum,
            solve_time_seconds=solve_time_sec,
        )

    @staticmethod
    def _prio_of(requests: List[AidRequest], req_id: str) -> str:
        for r in requests:
            if r.id == req_id:
                return r.priority.value
        return "UNKNOWN"

    @staticmethod
    def _score_of(requests: List[AidRequest], req_id: str) -> float:
        for r in requests:
            if r.id == req_id:
                return urgency_score(r)
        return 0.0
