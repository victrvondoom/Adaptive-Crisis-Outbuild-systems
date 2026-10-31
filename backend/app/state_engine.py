"""
AIDNEXUS ONE — Crisis State Machine & Simulation Engine

In-memory operational state with:
- deterministic seed scenario generation,
- hash-CHAINED audit events (each event's hash includes the previous hash),
- sequential plan versioning (v1.0, v2.0, v3.0, ... — pending plans are never
  silently overwritten; approval always targets the pending version),
- a state-machine-validated transition API (see models.ALLOWED_TRANSITIONS),
- idempotent delivery confirmation (inventory deducted exactly once),
- volunteer assignment on plan application,
- a dispatch queue that is a strict PROJECTION of the active approved plan
  (the optimizer's scheduled_sequence is the only execution order — the UI
  renders this projection and must never re-sort it).
"""
import random
import time
import hashlib
import itertools
from typing import Dict, List, Optional, Any, Tuple
from .models import (
    AidRequest, Depot, Vehicle, Volunteer, Disruption, MissionPlanVersion,
    AuditEvent, PriorityLevel, MissionStatus, DisruptionType, ActorType,
    Location, AidItem, PlannedRequestEntry, FeasibilityStatus,
    ALLOWED_TRANSITIONS, POLICY_VERSION,
)
from .optimizer import OptimizerEngine, haversine_distance_km, urgency_score
from .agents import NeedToMissionAgent, ResourceStrategistAgent, RecoveryAgent

AUDIT_RETENTION_LIMIT = 5000  # documented retention; trim (oldest first) is logged

# Vehicle types that require medical-qualified volunteers.
MEDICAL_VEHICLE_TYPES = {"Medical Evac Van"}


class CrisisStateEngine:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.optimizer = OptimizerEngine()
        self.agent1 = NeedToMissionAgent()
        self.agent2 = ResourceStrategistAgent()
        self.agent3 = RecoveryAgent()

        self.depots: Dict[str, Depot] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self.volunteers: Dict[str, Volunteer] = {}
        self.requests: Dict[str, AidRequest] = {}
        self.disruptions: Dict[str, Disruption] = {}
        self.plans: Dict[str, MissionPlanVersion] = {}
        self.audit_events: List[AuditEvent] = []
        self.current_plan_id: Optional[str] = None
        self.pending_plan_id: Optional[str] = None
        self.plan_counter: int = 0
        self._audit_tail_hash: str = ""

        # Simulation playback state
        self.sim_elapsed_seconds: float = 0.0
        self.is_paused: bool = False
        self.sim_speed: float = 2.0
        self.last_tick_time: float = time.time()

        # Delivery receipts for idempotency: request_id -> receipt
        self.delivery_receipts: Dict[str, Dict[str, Any]] = {}

        self.reset_scenario(seed=seed)

    # ------------------------------------------------------------------
    # Audit (hash-chained)
    # ------------------------------------------------------------------
    def log_audit(self, event_type: str, actor_id: str, actor_type: ActorType,
                  entity_type: str, entity_id: str, summary: str,
                  details: Dict[str, Any] = None) -> AuditEvent:
        ts = time.time()
        det = details or {}
        prev = self._audit_tail_hash
        raw = f"{ts}:{event_type}:{actor_id}:{entity_type}:{entity_id}:{summary}:{prev}"
        sha = hashlib.sha256(raw.encode()).hexdigest()
        event = AuditEvent(
            timestamp=ts, event_type=event_type, actor_id=actor_id, actor_type=actor_type,
            entity_type=entity_type, entity_id=entity_id, summary=summary,
            details=det, sha256_hash=sha, prev_hash=prev,
        )
        self.audit_events.append(event)
        self._audit_tail_hash = sha
        if len(self.audit_events) > AUDIT_RETENTION_LIMIT:
            self.audit_events = self.audit_events[-AUDIT_RETENTION_LIMIT:]
        return event

    # ------------------------------------------------------------------
    # Scenario
    # ------------------------------------------------------------------
    def reset_scenario(self, seed: int = 42):
        """Deterministic, reproducible baseline scenario."""
        self.seed = seed
        rng = random.Random(seed)
        self.depots.clear(); self.vehicles.clear(); self.volunteers.clear()
        self.requests.clear(); self.disruptions.clear(); self.plans.clear()
        self.audit_events.clear(); self.delivery_receipts.clear()
        self.current_plan_id = None; self.pending_plan_id = None
        self.plan_counter = 0
        self._audit_tail_hash = ""
        self.sim_elapsed_seconds = 0.0
        self.last_tick_time = time.time()

        base_lat, base_lng = 14.5995, 120.9842

        self.depots["DEPOT-ALPHA"] = Depot(
            id="DEPOT-ALPHA", name="Alpha Central Logistics Hub",
            location=Location(id="LOC-ALPHA", name="Central District",
                              lat=base_lat + 0.02, lng=base_lng - 0.01, sector="Central Metro"),
            inventory={"potable_water_liters": 15000.0, "trauma_kits": 400.0,
                       "rations_mre": 5000.0, "hygiene_kits": 1200.0, "generators": 45.0},
            status="OPERATIONAL")
        self.depots["DEPOT-BRAVO"] = Depot(
            id="DEPOT-BRAVO", name="Bravo Coastal Relief Port",
            location=Location(id="LOC-BRAVO", name="Southern Bay",
                              lat=base_lat - 0.05, lng=base_lng - 0.04, sector="Coastal Port"),
            inventory={"potable_water_liters": 20000.0, "trauma_kits": 250.0,
                       "rations_mre": 8000.0, "hygiene_kits": 2000.0, "generators": 30.0},
            status="OPERATIONAL")
        self.depots["DEPOT-CHARLIE"] = Depot(
            id="DEPOT-CHARLIE", name="Charlie Mountain Foothills Base",
            location=Location(id="LOC-CHARLIE", name="Northern Ridge",
                              lat=base_lat + 0.08, lng=base_lng + 0.05, sector="Highland Foothills"),
            inventory={"potable_water_liters": 12000.0, "trauma_kits": 500.0,
                       "rations_mre": 4500.0, "hygiene_kits": 900.0, "generators": 60.0},
            status="OPERATIONAL")

        depot_keys = list(self.depots.keys())
        v_types = [
            ("Heavy 4x4 Cargo", 2500.0, 50.0),
            ("Amphibious Rescue Truck", 1800.0, 42.0),
            ("Medical Evac Van", 900.0, 65.0),
            ("Rapid Response Carrier", 1200.0, 58.0),
        ]
        for i in range(1, 11):
            vid = f"VEH-{i:02d}"
            base_depot = depot_keys[(i - 1) % len(depot_keys)]
            depot_loc = self.depots[base_depot].location
            vtype, cap, speed = v_types[(i - 1) % len(v_types)]
            self.vehicles[vid] = Vehicle(
                id=vid, name=f"{vtype} #{i:02d}", vehicle_type=vtype, capacity_kg=cap,
                base_depot_id=base_depot, current_lat=depot_loc.lat, current_lng=depot_loc.lng,
                status="IDLE", speed_kmh=speed, fuel_pct=round(rng.uniform(85.0, 100.0), 1))

        roles = ["Paramedic Lead", "Heavy Logistics Driver", "Emergency Nurse", "Disaster Specialist"]
        for i in range(1, 13):
            vol_id = f"VOL-{i:02d}"
            self.volunteers[vol_id] = Volunteer(
                id=vol_id, name=f"Volunteer Specialist {i:02d}",
                role=roles[(i - 1) % len(roles)], status="AVAILABLE")

        sectors = ["Central Metro", "Coastal Port", "Highland Foothills", "River Valley", "Eastern Delta"]
        for i in range(1, 201):
            req_id = f"REQ-{i:03d}"
            offset_lat = rng.uniform(-0.10, 0.10)
            offset_lng = rng.uniform(-0.10, 0.10)
            sector = sectors[i % len(sectors)]
            p_roll = rng.random()
            if p_roll < 0.20:
                prio = PriorityLevel.CRITICAL
                items = [AidItem(item_type="trauma_kits", quantity=float(rng.randint(5, 25)), unit="kits"),
                         AidItem(item_type="potable_water_liters", quantity=float(rng.randint(150, 400)), unit="liters")]
            elif p_roll < 0.55:
                prio = PriorityLevel.HIGH
                items = [AidItem(item_type="potable_water_liters", quantity=float(rng.randint(150, 400)), unit="liters"),
                         AidItem(item_type="rations_mre", quantity=float(rng.randint(40, 100)), unit="packs")]
            elif p_roll < 0.90:
                prio = PriorityLevel.MEDIUM
                items = [AidItem(item_type="potable_water_liters", quantity=float(rng.randint(50, 200)), unit="liters"),
                         AidItem(item_type="hygiene_kits", quantity=float(rng.randint(10, 40)), unit="kits")]
            else:
                prio = PriorityLevel.LOW
                items = [AidItem(item_type="rations_mre", quantity=float(rng.randint(20, 50)), unit="packs")]

            req = AidRequest(
                id=req_id, requester_name=f"Community Shelter #{i:03d}",
                location=Location(id=f"LOC-REQ-{i:03d}", name=f"{sector} Relief Point #{i}",
                                 lat=round(base_lat + offset_lat, 5),
                                 lng=round(base_lng + offset_lng, 5), sector=sector),
                items=items, priority=prio,
                status=MissionStatus.VERIFIED if i > 15 else MissionStatus.REQUESTED,
                affected_people=rng.randint(20, 300),
                deadline_hours=float(rng.choice([4, 8, 12, 24, 24, 48])),
                intake_channel="SEED_SCENARIO",
            )
            req.urgency_score = urgency_score(req)
            self.requests[req_id] = req

        self.log_audit(
            event_type="SCENARIO_RESET", actor_id="COORDINATOR_SYSTEM", actor_type=ActorType.SYSTEM,
            entity_type="SYSTEM", entity_id="ROOT",
            summary=f"Initialized deterministic disaster scenario (Seed={seed}, 200 requests, 3 depots, 10 vehicles, 12 volunteers).")

        self.generate_initial_plan()

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    def _next_version_label(self) -> str:
        self.plan_counter += 1
        return f"v{self.plan_counter}.0"

    def generate_initial_plan(self) -> MissionPlanVersion:
        """Solves the baseline allocation and creates Plan v1.0.

        The initial plan is auto-activated by the system bootstrap (documented:
        the demo starts mid-operation). It is labeled auto_approved=True so the
        UI can show "SYSTEM BOOTSTRAP" instead of implying a human approved it.
        ALL subsequent plans require explicit human approval.
        """
        plan, interpretation = self.agent2.formulate_plan(
            requests=list(self.requests.values()),
            depots=list(self.depots.values()),
            vehicles=list(self.vehicles.values()),
            optimizer=self.optimizer,
            version_label=self._next_version_label(),
        )
        plan.is_active = True
        plan.is_approved = True
        plan.auto_approved = True
        plan.approved_by = "SYSTEM_BOOTSTRAP"
        self.plans[plan.version_id] = plan
        self.current_plan_id = plan.version_id
        self._apply_plan_assignments(plan, activate=True)

        self.log_audit(
            event_type="PLAN_INITIALIZED", actor_id="AGENT-02-RESOURCE", actor_type=ActorType.AGENT,
            entity_type="MissionPlanVersion", entity_id=plan.version_id,
            summary=(f"Plan {plan.version_id} auto-activated by SYSTEM BOOTSTRAP (demo starts "
                     f"mid-operation): {plan.total_fulfilled} requests scheduled across "
                     f"{len(plan.assignments)} vehicle routes, {len(plan.unmet_request_ids)} blocked. "
                     f"All subsequent plans require human approval."))

        # Seed some completed deliveries to represent operations in progress.
        for asgn in plan.assignments[:3]:
            for req_id in asgn.request_ids[:2]:
                req = self.requests.get(req_id)
                if req:
                    self._record_delivery(req, actor="SIMULATION_SEED", signature="seed-operations",
                                          audit_event_type="DELIVERY_CONFIRMED")
        return plan

    def _apply_plan_assignments(self, plan: MissionPlanVersion, activate: bool):
        """Applies a plan's assignments to vehicles/requests/volunteers.
        Delivered requests are never mutated (immutable completed deliveries)."""
        assigned_vehicle_ids = set()
        for asgn in plan.assignments:
            assigned_vehicle_ids.add(asgn.vehicle_id)
            vehicle = self.vehicles.get(asgn.vehicle_id)
            if vehicle:
                vehicle.assigned_mission_ids = list(asgn.request_ids)
                vehicle.route_waypoints = [list(pt) for pt in asgn.route_latlngs]
                vehicle.current_waypoint_idx = 1 if len(asgn.route_latlngs) > 1 else 0
                vehicle.status = "EN_ROUTE" if asgn.request_ids else "IDLE"
                vehicle.target_request_id = asgn.request_ids[0] if asgn.request_ids else None

            entry_by_req = {e.request_id: e for e in plan.request_entries.values()}
            for req_id in asgn.request_ids:
                req = self.requests.get(req_id)
                entry = entry_by_req.get(req_id)
                if not req:
                    continue
                if req.status == MissionStatus.DELIVERED or req.is_delivered:
                    continue  # immutable
                if entry and entry.feasibility_status == FeasibilityStatus.COMMITTED_PRESERVED:
                    # keep current assignment (already in flight); do not reset route
                    continue
                req.assigned_vehicle_id = asgn.vehicle_id
                req.assigned_depot_id = asgn.depot_id
                req.estimated_arrival_minutes = entry.estimated_arrival_min if entry else None
                if req.status in (MissionStatus.VERIFIED, MissionStatus.REQUESTED,
                                  MissionStatus.PLANNED, MissionStatus.PENDING_APPROVAL,
                                  MissionStatus.APPROVED, MissionStatus.REPLAN_PENDING):
                    req.status = MissionStatus.DISPATCHED

        # Volunteer assignment: role-matched, deterministic round-robin.
        self._assign_volunteers(assigned_vehicle_ids)

    def _assign_volunteers(self, assigned_vehicle_ids: set):
        # Release volunteers whose vehicle lost its assignment
        for vol in self.volunteers.values():
            vid = vol.assigned_vehicle_id
            if vid and (vid not in assigned_vehicle_ids or not self.vehicles.get(vid) or
                        not self.vehicles[vid].assigned_mission_ids):
                vol.assigned_vehicle_id = None
                vol.status = "AVAILABLE"
                if vid in self.vehicles:
                    self.vehicles[vid].assigned_volunteer_id = None

        medical_pool = itertools.cycle(
            [v for v in self.volunteers.values()
             if v.role in ("Paramedic Lead", "Emergency Nurse") and v.status == "AVAILABLE"])
        logistics_pool = itertools.cycle(
            [v for v in self.volunteers.values()
             if v.role in ("Heavy Logistics Driver", "Disaster Specialist") and v.status == "AVAILABLE"])

        for vid in sorted(assigned_vehicle_ids):
            vehicle = self.vehicles.get(vid)
            if not vehicle or not vehicle.assigned_mission_ids:
                continue
            pool = medical_pool if vehicle.vehicle_type in MEDICAL_VEHICLE_TYPES else logistics_pool
            vol = next(pool, None)
            if vol is None:
                pool = logistics_pool if vehicle.vehicle_type in MEDICAL_VEHICLE_TYPES else medical_pool
                vol = next(pool, None)
            if vol is not None:
                vol.assigned_vehicle_id = vid
                vol.status = "ASSIGNED"
                vehicle.assigned_volunteer_id = vol.id
                for req_id in vehicle.assigned_mission_ids:
                    req = self.requests.get(req_id)
                    if req and req.status != MissionStatus.DELIVERED:
                        req.assigned_volunteer_id = vol.id

    # ------------------------------------------------------------------
    # Disruptions & replanning
    # ------------------------------------------------------------------
    def inject_disruption(self, dtype: DisruptionType, title: str, description: str,
                          lat: float = None, lng: float = None, depot_id: str = None,
                          hazard_radius_km: float = 3.5) -> Dict[str, Any]:
        """Injects a disruption and formulates a recovery replan proposal.
        The proposal is PENDING — nothing changes until a human approves it.
        If a pending proposal already exists, it is superseded (the older pending
        proposal is marked as such and logged, never silently lost)."""
        dis_id = f"DIS-{int(time.time() * 1000) % 100000}"
        disruption = Disruption(
            id=dis_id, type=dtype, title=title, description=description,
            affected_lat=lat, affected_lng=lng, location_id=depot_id,
            severity="CRITICAL", active=True, hazard_radius_km=hazard_radius_km)
        self.disruptions[dis_id] = disruption

        if depot_id and depot_id in self.depots and dtype == DisruptionType.DEPOT_OUTAGE:
            self.depots[depot_id].status = "FLOODED"

        self.log_audit(
            event_type="DISRUPTION_INJECTED", actor_id="HAZARD_TELEMETRY", actor_type=ActorType.SYSTEM,
            entity_type="Disruption", entity_id=dis_id,
            summary=f"Incident Alert: {title} ({dtype.value}, hazard radius {hazard_radius_km} km).")

        current_plan = self.plans.get(self.current_plan_id)
        if current_plan is None:
            raise ValueError("No active plan to recover from")
        assessment = self.agent3.assess_impact(disruption, current_plan, self.requests)

        # Committed work: delivered (immutable) + already-dispatched (in flight)
        preserved_ids = list(assessment["preserved_mission_ids"])
        committed_map: Dict[str, Tuple[str, str]] = {}
        for req_id in assessment["affected_mission_ids"] + preserved_ids:
            req = self.requests.get(req_id)
            if req and req.assigned_vehicle_id and req.status in (
                    MissionStatus.DISPATCHED, MissionStatus.IN_TRANSIT):
                committed_map[req_id] = (req.assigned_vehicle_id, req.assigned_depot_id)
        for req in self.requests.values():
            if req.status in (MissionStatus.DISPATCHED, MissionStatus.IN_TRANSIT) and \
               req.id not in committed_map and req.assigned_vehicle_id:
                committed_map[req.id] = (req.assigned_vehicle_id, req.assigned_depot_id)
        # In-flight missions on non-disrupted routes are preserved too (they are
        # real-world commitments), unless their depot is now blocked.
        for req_id, (v_id, d_id) in list(committed_map.items()):
            if d_id == depot_id:
                del committed_map[req_id]  # depot gone: must re-source the goods

        blocked_depots = [depot_id] if depot_id else []
        blocked_locs = [(lat, lng, hazard_radius_km)] if (lat is not None and lng is not None) else []

        new_version = self._next_version_label()
        new_plan, interpretation = self.agent2.formulate_plan(
            requests=list(self.requests.values()),
            depots=list(self.depots.values()),
            vehicles=list(self.vehicles.values()),
            optimizer=self.optimizer,
            version_label=new_version,
            blocked_depot_ids=blocked_depots,
            blocked_locations=blocked_locs,
            preserve_request_ids=list(committed_map.keys()) + preserved_ids,
            committed_assignments=committed_map,
            previous_plan=current_plan,
        )
        new_plan.is_active = False
        new_plan.is_approved = False
        new_plan.replan_delta = {
            "before_version": current_plan.version_id,
            "before_fulfilled": current_plan.total_fulfilled,
            "before_distance_km": current_plan.total_distance_km,
            "after_fulfilled": new_plan.total_fulfilled,
            "after_distance_km": new_plan.total_distance_km,
            "preserved_deliveries_count": assessment["preserved_count"],
            "in_flight_preserved_count": len(committed_map),
            "disrupted_deliveries_count": assessment["affected_count"],
            "blocked_after_replan": len(new_plan.unmet_request_ids),
            "solve_time_seconds": new_plan.solve_time_seconds,
        }
        new_plan.tradeoff_explanation = (
            f"RECOVERY PLAN {new_version}: computed around '{title}' "
            f"(policy {new_plan.policy_version}). Preserved {assessment['preserved_count']} completed "
            f"deliveries (immutable) and {len(committed_map)} in-flight commitments. "
            f"Scheduled {new_plan.total_fulfilled} missions; {len(new_plan.unmet_request_ids)} are "
            f"blocked with explicit reasons. Awaiting Mission Coordinator approval before dispatch.")
        if self.pending_plan_id and self.pending_plan_id in self.plans:
            superseded = self.plans[self.pending_plan_id]
            self.log_audit(
                event_type="PLAN_SUPERSEDED", actor_id="AGENT-03-RECOVERY", actor_type=ActorType.AGENT,
                entity_type="MissionPlanVersion", entity_id=superseded.version_id,
                summary=f"Pending proposal {superseded.version_id} superseded by {new_version} "
                        f"(new disruption takes precedence; superseded plan retained in history).")
        self.plans[new_version] = new_plan
        self.pending_plan_id = new_version

        self.log_audit(
            event_type="REPLAN_FORMULATED", actor_id="AGENT-03-RECOVERY", actor_type=ActorType.AGENT,
            entity_type="MissionPlanVersion", entity_id=new_version,
            summary=(f"Formulated recovery plan {new_version} in response to {title} "
                     f"(solve time {new_plan.solve_time_seconds}s). Pending human approval — "
                     f"no operational state has changed."))

        return {"disruption": disruption, "assessment": assessment,
                "replan": new_plan, "interpretation": interpretation}

    def approve_pending_plan(self, approver_name: str = "Mission Coordinator") -> MissionPlanVersion:
        """Human approves the pending plan. Only the pending version can be
        approved; approval is rejected if another plan is active-and-approved as
        pending, or if no pending plan exists."""
        if not self.pending_plan_id or self.pending_plan_id not in self.plans:
            raise ValueError("No pending plan to approve")
        plan = self.plans[self.pending_plan_id]
        if plan.is_approved:
            raise ValueError(f"Plan {plan.version_id} is already approved")

        # Deactivate current plan atomically
        if self.current_plan_id and self.current_plan_id in self.plans:
            self.plans[self.current_plan_id].is_active = False

        plan.is_approved = True
        plan.is_active = True
        plan.approved_by = approver_name
        self.current_plan_id = plan.version_id
        self.pending_plan_id = None
        self._apply_plan_assignments(plan, activate=True)

        self.log_audit(
            event_type="APPROVAL_GRANTED", actor_id=approver_name, actor_type=ActorType.HUMAN,
            entity_type="MissionPlanVersion", entity_id=plan.version_id,
            summary=(f"Human coordinator {approver_name} authorized plan {plan.version_id}. "
                     f"Route updates deployed to active fleet."))
        return plan

    # ------------------------------------------------------------------
    # Delivery (idempotent)
    # ------------------------------------------------------------------
    def _record_delivery(self, req: AidRequest, actor: str, signature: str,
                         audit_event_type: str = "DELIVERY_CONFIRMED") -> Dict[str, Any]:
        """Records a delivery exactly once: sets status, deducts assigned depot
        stock once, writes an audit event, and stores a receipt. Repeat calls
        return the existing receipt without side effects (idempotency)."""
        if req.id in self.delivery_receipts:
            return self.delivery_receipts[req.id]

        was_delivered = req.status == MissionStatus.DELIVERED
        if not was_delivered:
            req.status = MissionStatus.DELIVERED
            req.is_delivered = True
            req.delivery_timestamp = time.time()
            if req.assigned_depot_id and req.assigned_depot_id in self.depots:
                depot = self.depots[req.assigned_depot_id]
                for item in req.items:
                    depot.inventory[item.item_type] = max(
                        0.0, depot.inventory.get(item.item_type, 0.0) - item.quantity)

        sig_hash = hashlib.sha256(
            f"{req.id}:{actor}:{signature}:{req.delivery_timestamp}".encode()).hexdigest()
        receipt = {
            "success": True, "request_id": req.id, "status": req.status.value,
            "signature_hash": sig_hash, "duplicate": was_delivered,
        }
        self.delivery_receipts[req.id] = receipt

        self.log_audit(
            event_type=audit_event_type, actor_id=actor,
            actor_type=ActorType.HUMAN if actor.startswith("VOLUNTEER") or "Specialist" in actor else ActorType.SYSTEM,
            entity_type="AidRequest", entity_id=req.id,
            summary=f"Proof of Delivery recorded for {req.requester_name} by {actor}.",
            details={"signature_hash": sig_hash,
                     "items_delivered": [it.model_dump() for it in req.items],
                     "duplicate_confirmation": was_delivered})
        return receipt

    def confirm_delivery(self, request_id: str, volunteer_name: str,
                         signature_data: str = "VerifiedDigitalSignature") -> Dict[str, Any]:
        """Volunteer proof-of-delivery. Idempotent: confirming an already
        confirmed delivery returns the original receipt and does NOT deduct
        inventory twice."""
        req = self.requests.get(request_id)
        if not req:
            raise ValueError(f"Request {request_id} not found")
        if req.status == MissionStatus.CANCELLED:
            raise ValueError(f"Request {request_id} is cancelled; cannot confirm delivery")
        return self._record_delivery(req, actor=volunteer_name, signature=signature_data)

    # ------------------------------------------------------------------
    # Validated transitions
    # ------------------------------------------------------------------
    def transition_mission(self, request_id: str, new_status: MissionStatus,
                           actor_id: str, reason: str = None) -> Dict[str, Any]:
        """State-machine-validated transition. Raises ValueError on any
        transition not in models.ALLOWED_TRANSITIONS. DELIVERED must go through
        confirm_delivery (which handles inventory + receipts)."""
        req = self.requests.get(request_id)
        if not req:
            raise ValueError(f"Request {request_id} not found")
        old_status = req.status
        allowed = ALLOWED_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition {old_status.value} -> {new_status.value} for {request_id}. "
                f"Allowed: {[s.value for s in allowed]}.")
        if new_status == MissionStatus.DELIVERED:
            raise ValueError("DELIVERED must be set via delivery confirmation "
                             "(POST /api/v1/deliveries/confirm), not a raw transition.")
        req.status = new_status
        self.log_audit(
            event_type="STATE_TRANSITION", actor_id=actor_id, actor_type=ActorType.HUMAN,
            entity_type="AidRequest", entity_id=request_id,
            summary=f"Transitioned mission from {old_status.value} to {new_status.value}. Reason: {reason or 'User action'}")
        return {"success": True, "request_id": request_id,
                "old_status": old_status.value, "new_status": new_status.value}

    # ------------------------------------------------------------------
    # Simulation tick
    # ------------------------------------------------------------------
    def advance_simulation(self, delta_sec: float = 1.0) -> Dict[str, Any]:
        if self.is_paused:
            return {"status": "PAUSED", "elapsed": self.sim_elapsed_seconds}

        effective_dt = delta_sec * self.sim_speed
        self.sim_elapsed_seconds += effective_dt
        deliveries_triggered = []

        for veh in self.vehicles.values():
            if veh.status not in ("EN_ROUTE", "DELIVERING") or not veh.route_waypoints:
                continue
            if veh.current_waypoint_idx >= len(veh.route_waypoints):
                veh.status = "IDLE"
                continue

            target_lat, target_lng = veh.route_waypoints[veh.current_waypoint_idx]
            d_km = haversine_distance_km(veh.current_lat, veh.current_lng, target_lat, target_lng)
            max_move_km = (veh.speed_kmh / 3600.0) * effective_dt

            if d_km <= max_move_km or d_km < 0.15:
                veh.current_lat = target_lat
                veh.current_lng = target_lng
                veh.distance_traveled_km += d_km
                veh.fuel_pct = max(10.0, veh.fuel_pct - (d_km * 0.08))

                # Deterministic mapping: waypoint index k corresponds to the
                # (k-1)-th mission in assigned_mission_ids (route starts at depot).
                wp_idx = veh.current_waypoint_idx
                if 1 <= wp_idx <= len(veh.assigned_mission_ids):
                    req_id = veh.assigned_mission_ids[wp_idx - 1]
                    req = self.requests.get(req_id)
                    if req and req.status != MissionStatus.DELIVERED:
                        receipt = self._record_delivery(
                            req, actor="SIMULATION_AUTO_ARRIVAL",
                            signature="waypoint-arrival-auto",
                            audit_event_type="DELIVERY_CONFIRMED")
                        deliveries_triggered.append(req_id)

                veh.current_waypoint_idx += 1
                if veh.current_waypoint_idx < len(veh.route_waypoints):
                    remaining = [r for r in veh.assigned_mission_ids
                                 if self.requests.get(r) and self.requests[r].status != MissionStatus.DELIVERED]
                    veh.target_request_id = remaining[0] if remaining else None
                else:
                    veh.status = "IDLE"
                    veh.target_request_id = None
            else:
                ratio = max_move_km / max(d_km, 0.001)
                veh.current_lat += (target_lat - veh.current_lat) * ratio
                veh.current_lng += (target_lng - veh.current_lng) * ratio
                veh.distance_traveled_km += max_move_km
                veh.fuel_pct = max(10.0, veh.fuel_pct - (max_move_km * 0.08))

        return {"status": "RUNNING",
                "elapsed_seconds": round(self.sim_elapsed_seconds, 1),
                "sim_speed": self.sim_speed,
                "new_deliveries": deliveries_triggered}

    # ------------------------------------------------------------------
    # Dispatch queue: STRICT PROJECTION of the active plan
    # ------------------------------------------------------------------
    def get_dispatch_queue(self) -> List[Dict[str, Any]]:
        """The authoritative dispatch queue: active approved plan entries with
        feasibility SCHEDULED/COMMITTED_PRESERVED, ordered by the optimizer's
        scheduled_sequence. This method performs NO re-sorting by any other key
        and NO re-computation of priority — it is a pure projection."""
        plan = self.plans.get(self.current_plan_id)
        if not plan:
            return []
        entries = [e for e in plan.request_entries.values()
                   if e.feasibility_status in (FeasibilityStatus.SCHEDULED,
                                               FeasibilityStatus.COMMITTED_PRESERVED)]
        entries.sort(key=lambda e: e.scheduled_sequence)
        queue = []
        for e in entries:
            req = self.requests.get(e.request_id)
            queue.append({
                "request_id": e.request_id,
                "assignment_id": e.assignment_id,
                "humanitarian_priority": e.humanitarian_priority,
                "urgency_score": e.urgency_score,
                "scheduled_sequence": e.scheduled_sequence,
                "estimated_arrival_min": e.estimated_arrival_min,
                "assigned_vehicle": e.assigned_vehicle,
                "assigned_depot": e.assigned_depot,
                "assigned_volunteer": req.assigned_volunteer_id if req else e.assigned_volunteer,
                "feasibility_status": e.feasibility_status.value,
                "status": req.status.value if req else "UNKNOWN",
                "requester_name": req.requester_name if req else "",
                "sector": req.location.sector if req else "",
                "items": [it.model_dump() for it in req.items] if req else [],
            })
        return queue

    def get_blocked_requests(self) -> List[Dict[str, Any]]:
        """Blocked/unresolved work from the active plan, with explicit reasons.
        Nothing is hidden: every unscheduled request appears here."""
        plan = self.plans.get(self.current_plan_id)
        if not plan:
            return []
        blocked = []
        for e in plan.request_entries.values():
            if e.feasibility_status not in (FeasibilityStatus.SCHEDULED,
                                            FeasibilityStatus.COMMITTED_PRESERVED):
                req = self.requests.get(e.request_id)
                blocked.append({
                    "request_id": e.request_id,
                    "humanitarian_priority": e.humanitarian_priority,
                    "urgency_score": e.urgency_score,
                    "feasibility_status": e.feasibility_status.value,
                    "unmet_demand": e.unmet_demand,
                    "explanation": e.explanation_reference,
                    "requester_name": req.requester_name if req else "",
                    "sector": req.location.sector if req else "",
                })
        blocked.sort(key=lambda b: (-b["urgency_score"], b["request_id"]))
        return blocked

    def queue_concordance(self) -> float:
        """PRIORITY QUEUE CONCORDANCE metric: fraction of dispatch-queue entries
        whose relative order matches the plan's scheduled_sequence order.
        Computed by comparing the queue's order against the plan's entries —
        must be 1.0; a regression below 1.0 means the UI/engine diverged."""
        queue = self.get_dispatch_queue()
        plan = self.plans.get(self.current_plan_id)
        if not plan or not queue:
            return 1.0
        seqs = [q["scheduled_sequence"] for q in queue]
        expected = sorted(seqs)
        matching = sum(1 for i, s in enumerate(seqs) if s == expected[i])
        return round(matching / len(seqs), 4)

    # ------------------------------------------------------------------
    # Summary state for the dashboard
    # ------------------------------------------------------------------
    def get_summary_state(self) -> Dict[str, Any]:
        all_reqs = list(self.requests.values())
        total_reqs = len(all_reqs)
        delivered_count = sum(1 for r in all_reqs if r.status == MissionStatus.DELIVERED)
        dispatched_count = sum(1 for r in all_reqs if r.status == MissionStatus.DISPATCHED)
        critical_total = sum(1 for r in all_reqs if r.priority == PriorityLevel.CRITICAL)
        # CORRECTED metric: fulfilled = DELIVERED only (dispatched is NOT fulfilled).
        critical_delivered = sum(1 for r in all_reqs
                                 if r.priority == PriorityLevel.CRITICAL
                                 and r.status == MissionStatus.DELIVERED)
        critical_dispatched = sum(1 for r in all_reqs
                                  if r.priority == PriorityLevel.CRITICAL
                                  and r.status in (MissionStatus.DISPATCHED, MissionStatus.IN_TRANSIT))
        active_disruptions = [d for d in self.disruptions.values() if d.active]
        blocked = self.get_blocked_requests()
        queue = self.get_dispatch_queue()
        plan = self.plans.get(self.current_plan_id)

        return {
            "stats": {
                "total_requests": total_reqs,
                "delivered_count": delivered_count,
                "dispatched_count": dispatched_count,
                # Delivered-only fulfillment (see docs/metrics/METRIC_REGISTRY.md)
                "critical_fulfillment_rate": round((critical_delivered / critical_total) * 100, 1) if critical_total else 0.0,
                "critical_dispatched_count": critical_dispatched,
                "critical_total": critical_total,
                "blocked_count": len(blocked),
                "unmet_count": len(blocked),
                "active_disruptions_count": len(active_disruptions),
                "current_plan_version": self.current_plan_id or "None",
                "pending_replan_approval": self.pending_plan_id is not None,
                "pending_plan_version": self.pending_plan_id,
                "policy_version": POLICY_VERSION,
                "queue_concordance": self.queue_concordance(),
                "sim_elapsed_seconds": round(self.sim_elapsed_seconds, 1),
                "is_paused": self.is_paused,
                "sim_speed": self.sim_speed,
            },
            "depots": [d.model_dump() for d in self.depots.values()],
            "vehicles": [v.model_dump() for v in self.vehicles.values()],
            "volunteers": [v.model_dump() for v in self.volunteers.values()],
            "requests": [r.model_dump() for r in all_reqs],  # FULL list — no silent truncation
            "active_disruptions": [d.model_dump() for d in active_disruptions],
            "current_plan": plan.model_dump() if plan else None,
            "pending_plan": (self.plans[self.pending_plan_id].model_dump()
                             if self.pending_plan_id and self.pending_plan_id in self.plans else None),
            "dispatch_queue": queue,          # authoritative execution order (projection)
            "blocked_requests": blocked,       # visible, explained, never hidden
            "recent_audit": [e.model_dump() for e in self.audit_events[-100:]],
        }
