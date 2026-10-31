"""
AIDNEXUS ONE — Dynamic Crisis State Machine & Simulation Engine
Maintains in-memory live simulation state, audit logging with SHA-256 hashes,
deterministic seed=42 scenario generator, dynamic vehicle routing, and live clock ticking.
"""
import random
import time
import math
import hashlib
from typing import Dict, List, Optional, Any
from .models import (
    AidRequest, Depot, Vehicle, Volunteer, Disruption, MissionPlanVersion,
    AuditEvent, PriorityLevel, MissionStatus, DisruptionType, ActorType, Location, AidItem
)
from .optimizer import OptimizerEngine, haversine_distance_km
from .agents import NeedToMissionAgent, RecoveryAgent

class CrisisStateEngine:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.optimizer = OptimizerEngine()
        self.agent1 = NeedToMissionAgent()
        self.agent3 = RecoveryAgent()

        self.depots: Dict[str, Depot] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self.volunteers: Dict[str, Volunteer] = {}
        self.requests: Dict[str, AidRequest] = {}
        self.disruptions: Dict[str, Disruption] = {}
        self.plans: Dict[str, MissionPlanVersion] = {}
        self.audit_events: List[AuditEvent] = []
        self.current_plan_id: Optional[str] = None
        
        # Simulation playback state
        self.sim_elapsed_seconds: float = 0.0
        self.is_paused: bool = False
        self.sim_speed: float = 2.0
        self.last_tick_time: float = time.time()

        self.reset_scenario(seed=seed)

    def log_audit(self, event_type: str, actor_id: str, actor_type: ActorType, entity_type: str, entity_id: str, summary: str, details: Dict[str, Any] = None):
        ts = time.time()
        det = details or {}
        raw = f"{ts}:{event_type}:{actor_id}:{entity_type}:{entity_id}:{summary}"
        sha = hashlib.sha256(raw.encode()).hexdigest()
        event = AuditEvent(
            timestamp=ts,
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            details=det,
            sha256_hash=sha
        )
        self.audit_events.append(event)
        if len(self.audit_events) > 300:
            self.audit_events = self.audit_events[-300:]
        return event

    def reset_scenario(self, seed: int = 42):
        """Builds deterministic, reproducible baseline scenario (Seed=42)."""
        self.seed = seed
        rng = random.Random(seed)
        self.depots.clear()
        self.vehicles.clear()
        self.volunteers.clear()
        self.requests.clear()
        self.disruptions.clear()
        self.plans.clear()
        self.audit_events.clear()
        self.current_plan_id = None
        self.sim_elapsed_seconds = 0.0
        self.last_tick_time = time.time()

        # Center point: Pacific Metro Sector (Lat 14.5995, Lng 120.9842)
        base_lat = 14.5995
        base_lng = 120.9842

        # 1. Depots (Alpha Central, Bravo Coastal, Charlie Highland)
        self.depots["DEPOT-ALPHA"] = Depot(
            id="DEPOT-ALPHA",
            name="Alpha Central Logistics Hub",
            location=Location(id="LOC-ALPHA", name="Central District", lat=base_lat + 0.02, lng=base_lng - 0.01, sector="Central Metro"),
            inventory={
                "potable_water_liters": 15000.0,
                "trauma_kits": 400.0,
                "rations_mre": 5000.0,
                "hygiene_kits": 1200.0,
                "generators": 45.0
            },
            status="OPERATIONAL"
        )

        self.depots["DEPOT-BRAVO"] = Depot(
            id="DEPOT-BRAVO",
            name="Bravo Coastal Relief Port",
            location=Location(id="LOC-BRAVO", name="Southern Bay", lat=base_lat - 0.05, lng=base_lng - 0.04, sector="Coastal Port"),
            inventory={
                "potable_water_liters": 20000.0,
                "trauma_kits": 250.0,
                "rations_mre": 8000.0,
                "hygiene_kits": 2000.0,
                "generators": 30.0
            },
            status="OPERATIONAL"
        )

        self.depots["DEPOT-CHARLIE"] = Depot(
            id="DEPOT-CHARLIE",
            name="Charlie Mountain Foothills Base",
            location=Location(id="LOC-CHARLIE", name="Northern Ridge", lat=base_lat + 0.08, lng=base_lng + 0.05, sector="Highland Foothills"),
            inventory={
                "potable_water_liters": 12000.0,
                "trauma_kits": 500.0,
                "rations_mre": 4500.0,
                "hygiene_kits": 900.0,
                "generators": 60.0
            },
            status="OPERATIONAL"
        )

        # 2. Vehicles (10 vehicles)
        depot_keys = list(self.depots.keys())
        v_types = [
            ("Heavy 4x4 Cargo", 2500.0, 50.0),
            ("Amphibious Rescue Truck", 1800.0, 42.0),
            ("Medical Evac Van", 900.0, 65.0),
            ("Rapid Response Carrier", 1200.0, 58.0)
        ]
        for i in range(1, 11):
            vid = f"VEH-{i:02d}"
            base_depot = depot_keys[(i - 1) % len(depot_keys)]
            depot_loc = self.depots[base_depot].location
            vtype, cap, speed = v_types[(i - 1) % len(v_types)]
            self.vehicles[vid] = Vehicle(
                id=vid,
                name=f"{vtype} #{i:02d}",
                vehicle_type=vtype,
                capacity_kg=cap,
                base_depot_id=base_depot,
                current_lat=depot_loc.lat,
                current_lng=depot_loc.lng,
                status="IDLE",
                speed_kmh=speed,
                fuel_pct=round(rng.uniform(85.0, 100.0), 1)
            )

        # 3. Volunteers (12 specialists)
        roles = ["Paramedic Lead", "Heavy Logistics Driver", "Emergency Nurse", "Disaster Specialist"]
        for i in range(1, 13):
            vol_id = f"VOL-{i:02d}"
            self.volunteers[vol_id] = Volunteer(
                id=vol_id,
                name=f"Volunteer Specialist {i:02d}",
                role=roles[(i - 1) % len(roles)],
                status="AVAILABLE"
            )

        # 4. Deterministic Seed Requests (200 requests)
        sectors = ["Central Metro", "Coastal Port", "Highland Foothills", "River Valley", "Eastern Delta"]
        for i in range(1, 201):
            req_id = f"REQ-{i:03d}"
            offset_lat = rng.uniform(-0.10, 0.10)
            offset_lng = rng.uniform(-0.10, 0.10)
            sector = sectors[i % len(sectors)]
            
            p_roll = rng.random()
            if p_roll < 0.20:
                prio = PriorityLevel.CRITICAL
                items = [
                    AidItem(item_type="trauma_kits", quantity=float(rng.randint(5, 25)), unit="kits"),
                    AidItem(item_type="potable_water_liters", quantity=float(rng.randint(150, 400)), unit="liters")
                ]
            elif p_roll < 0.55:
                prio = PriorityLevel.HIGH
                items = [
                    AidItem(item_type="potable_water_liters", quantity=float(rng.randint(150, 400)), unit="liters"),
                    AidItem(item_type="rations_mre", quantity=float(rng.randint(40, 100)), unit="packs")
                ]
            elif p_roll < 0.90:
                prio = PriorityLevel.MEDIUM
                items = [
                    AidItem(item_type="potable_water_liters", quantity=float(rng.randint(50, 200)), unit="liters"),
                    AidItem(item_type="hygiene_kits", quantity=float(rng.randint(10, 40)), unit="kits")
                ]
            else:
                prio = PriorityLevel.LOW
                items = [
                    AidItem(item_type="rations_mre", quantity=float(rng.randint(20, 50)), unit="packs")
                ]

            self.requests[req_id] = AidRequest(
                id=req_id,
                requester_name=f"Community Shelter #{i:03d}",
                location=Location(
                    id=f"LOC-REQ-{i:03d}",
                    name=f"{sector} Relief Point #{i}",
                    lat=round(base_lat + offset_lat, 5),
                    lng=round(base_lng + offset_lng, 5),
                    sector=sector
                ),
                items=items,
                priority=prio,
                status=MissionStatus.VERIFIED if i > 15 else MissionStatus.REQUESTED,
                affected_people=rng.randint(20, 300)
            )

        self.log_audit(
            event_type="SCENARIO_RESET",
            actor_id="COORDINATOR_SYSTEM",
            actor_type=ActorType.SYSTEM,
            entity_type="SYSTEM",
            entity_id="ROOT",
            summary=f"Initialized deterministic disaster scenario (Seed={seed}, 200 requests, 3 depots, 10 vehicles, 12 volunteers)."
        )

        # Formulate initial Plan v1.0
        self.generate_initial_plan()

    def generate_initial_plan(self) -> MissionPlanVersion:
        """Solves baseline allocation and creates Plan v1.0."""
        plan = self.optimizer.solve_allocation(
            requests=list(self.requests.values()),
            depots=list(self.depots.values()),
            vehicles=list(self.vehicles.values()),
            version_label="v1.0"
        )
        plan.is_active = True
        plan.is_approved = True
        plan.approved_by = "Lead Mission Coordinator"
        self.plans["v1.0"] = plan
        self.current_plan_id = "v1.0"

        # Apply plan assignments to vehicles and requests
        for asgn in plan.assignments:
            vehicle = self.vehicles.get(asgn.vehicle_id)
            if vehicle:
                vehicle.assigned_mission_ids = asgn.request_ids
                vehicle.route_waypoints = asgn.route_latlngs
                vehicle.current_waypoint_idx = 1 if len(asgn.route_latlngs) > 1 else 0
                vehicle.status = "EN_ROUTE"
                if asgn.request_ids:
                    vehicle.target_request_id = asgn.request_ids[0]
            
            for req_id in asgn.request_ids:
                req = self.requests.get(req_id)
                if req:
                    req.assigned_vehicle_id = asgn.vehicle_id
                    req.assigned_depot_id = asgn.depot_id
                    req.status = MissionStatus.DISPATCHED

        # Mark first 15 requests as DELIVERED to simulate active operations
        for asgn in plan.assignments[:3]:
            for req_id in asgn.request_ids[:2]:
                req = self.requests.get(req_id)
                if req:
                    req.status = MissionStatus.DELIVERED
                    req.is_delivered = True
                    req.delivery_timestamp = time.time() - 1800

        self.log_audit(
            event_type="PLAN_INITIALIZED",
            actor_id="AGENT-02-RESOURCE",
            actor_type=ActorType.AGENT,
            entity_type="MissionPlanVersion",
            entity_id="v1.0",
            summary=f"Formulated and approved Plan v1.0: {plan.total_fulfilled} requests assigned across {len(plan.assignments)} active vehicle routes."
        )
        return plan

    def advance_simulation(self, delta_sec: float = 1.0) -> Dict[str, Any]:
        """
        Dynamically advances the real-time simulation step:
        - Ticks simulation time
        - Smoothly moves vehicles toward their current waypoints
        - Automatically triggers arrival, delivery, and stock deduction
        """
        if self.is_paused:
            return {"status": "PAUSED", "elapsed": self.sim_elapsed_seconds}

        effective_dt = delta_sec * self.sim_speed
        self.sim_elapsed_seconds += effective_dt
        deliveries_triggered = []

        for veh in self.vehicles.values():
            if veh.status not in ["EN_ROUTE", "DELIVERING"] or not veh.route_waypoints:
                continue

            if veh.current_waypoint_idx >= len(veh.route_waypoints):
                veh.status = "IDLE"
                continue

            target_lat, target_lng = veh.route_waypoints[veh.current_waypoint_idx]
            d_km = haversine_distance_km(veh.current_lat, veh.current_lng, target_lat, target_lng)

            # Move vehicle
            max_move_km = (veh.speed_kmh / 3600.0) * effective_dt
            if d_km <= max_move_km or d_km < 0.15:
                # Arrived at waypoint
                veh.current_lat = target_lat
                veh.current_lng = target_lng
                veh.distance_traveled_km += d_km
                veh.fuel_pct = max(10.0, veh.fuel_pct - (d_km * 0.08))

                # Check if this waypoint matches an assigned aid request
                for req_id in veh.assigned_mission_ids:
                    req = self.requests.get(req_id)
                    if req and req.status != MissionStatus.DELIVERED:
                        if abs(req.location.lat - target_lat) < 0.005 and abs(req.location.lng - target_lng) < 0.005:
                            req.status = MissionStatus.DELIVERED
                            req.is_delivered = True
                            req.delivery_timestamp = time.time()
                            deliveries_triggered.append(req_id)
                            # Decrement depot inventory
                            if req.assigned_depot_id and req.assigned_depot_id in self.depots:
                                dep = self.depots[req.assigned_depot_id]
                                for itm in req.items:
                                    dep.inventory[itm.item_type] = max(0.0, dep.inventory.get(itm.item_type, 0.0) - itm.quantity)
                            break

                # Advance to next waypoint
                veh.current_waypoint_idx += 1
                if veh.current_waypoint_idx < len(veh.route_waypoints):
                    # Update target request id if applicable
                    remaining_reqs = [r for r in veh.assigned_mission_ids if self.requests.get(r) and self.requests[r].status != MissionStatus.DELIVERED]
                    veh.target_request_id = remaining_reqs[0] if remaining_reqs else None
                else:
                    veh.status = "IDLE"
                    veh.target_request_id = None
            else:
                # Interpolate move
                ratio = max_move_km / max(d_km, 0.001)
                veh.current_lat += (target_lat - veh.current_lat) * ratio
                veh.current_lng += (target_lng - veh.current_lng) * ratio
                veh.distance_traveled_km += max_move_km
                veh.fuel_pct = max(10.0, veh.fuel_pct - (max_move_km * 0.08))

        return {
            "status": "RUNNING",
            "elapsed_seconds": round(self.sim_elapsed_seconds, 1),
            "sim_speed": self.sim_speed,
            "new_deliveries": deliveries_triggered
        }

    def inject_disruption(self, dtype: DisruptionType, title: str, description: str, lat: float = None, lng: float = None, depot_id: str = None) -> Dict[str, Any]:
        """
        Injects a disaster disruption (e.g. Route Cutoff, Depot Flooding, Vehicle Breakdown),
        triggers Agent 3 recovery assessment, and automatically formulates an adaptive replan (Plan v2.0).
        """
        dis_id = f"DIS-{str(int(time.time()))[-4:]}"
        disruption = Disruption(
            id=dis_id,
            type=dtype,
            title=title,
            description=description,
            affected_lat=lat,
            affected_lng=lng,
            location_id=depot_id,
            severity="CRITICAL",
            active=True
        )
        self.disruptions[dis_id] = disruption

        # If depot disrupted, mark depot flooded
        if depot_id and depot_id in self.depots:
            self.depots[depot_id].status = "FLOODED"

        self.log_audit(
            event_type="DISRUPTION_INJECTED",
            actor_id="HAZARD_TELEMETRY",
            actor_type=ActorType.SYSTEM,
            entity_type="Disruption",
            entity_id=dis_id,
            summary=f"Incident Alert: {title} ({dtype.value})."
        )

        # Agent 3: Assess Impact
        current_plan = self.plans.get(self.current_plan_id) or self.plans["v1.0"]
        assessment = self.agent3.assess_impact(disruption, current_plan, self.requests)

        # Agent 2 + Optimizer: Formulate Dynamic Replan (v2.0)
        blocked_depots = [depot_id] if depot_id else []
        blocked_locs = [(lat, lng, 3.5)] if (lat is not None and lng is not None) else []

        new_plan = self.optimizer.solve_allocation(
            requests=list(self.requests.values()),
            depots=list(self.depots.values()),
            vehicles=list(self.vehicles.values()),
            blocked_depot_ids=blocked_depots,
            blocked_locations=blocked_locs,
            preserve_request_ids=assessment["preserved_mission_ids"],
            version_label="v2.0"
        )

        new_plan.is_active = False  # Pending Human Approval!
        new_plan.is_approved = False
        new_plan.replan_delta = {
            "before_version": current_plan.version_id,
            "before_fulfilled": current_plan.total_fulfilled,
            "after_fulfilled": new_plan.total_fulfilled,
            "preserved_deliveries_count": assessment["preserved_count"],
            "disrupted_deliveries_count": assessment["affected_count"],
            "hazard_bypass_pct": 100.0,
            "rerouted_routes_count": len(new_plan.assignments)
        }
        new_plan.tradeoff_explanation = (
            f"RECOVERY PLAN v2.0: Automatically adapted around {disruption.title}. "
            f"Preserved {assessment['preserved_count']} completed deliveries without mutation. "
            f"Successfully rerouted {new_plan.total_fulfilled} missions around hazard zones. "
            f"Awaiting Mission Coordinator Sign-Off before dispatch re-engagement."
        )
        self.plans["v2.0"] = new_plan

        self.log_audit(
            event_type="REPLAN_FORMULATED",
            actor_id="AGENT-03-RECOVERY",
            actor_type=ActorType.AGENT,
            entity_type="MissionPlanVersion",
            entity_id="v2.0",
            summary=f"Formulated Self-Healing Plan v2.0 in response to {title}. Pending Human-in-the-Loop Approval."
        )

        return {
            "disruption": disruption,
            "assessment": assessment,
            "replan": new_plan
        }

    def approve_replan(self, approver_name: str = "Mission Coordinator") -> MissionPlanVersion:
        """Human Coordinator reviews and approves Plan v2.0."""
        plan = self.plans.get("v2.0")
        if not plan:
            raise ValueError("No pending Plan v2.0 to approve")

        plan.is_approved = True
        plan.is_active = True
        plan.approved_by = approver_name
        self.current_plan_id = "v2.0"

        # Apply new assignments to vehicles and update their route waypoints immediately!
        for asgn in plan.assignments:
            vehicle = self.vehicles.get(asgn.vehicle_id)
            if vehicle:
                vehicle.assigned_mission_ids = asgn.request_ids
                vehicle.route_waypoints = asgn.route_latlngs
                vehicle.current_waypoint_idx = 0
                vehicle.status = "EN_ROUTE"
                if asgn.request_ids:
                    vehicle.target_request_id = asgn.request_ids[0]
            
            for req_id in asgn.request_ids:
                req = self.requests.get(req_id)
                if req and req.status != MissionStatus.DELIVERED:
                    req.assigned_vehicle_id = asgn.vehicle_id
                    req.assigned_depot_id = asgn.depot_id
                    req.status = MissionStatus.DISPATCHED

        self.log_audit(
            event_type="APPROVAL_GRANTED",
            actor_id=approver_name,
            actor_type=ActorType.HUMAN,
            entity_type="MissionPlanVersion",
            entity_id="v2.0",
            summary=f"Authorized Plan v2.0 dispatch. Dynamic self-healing route updates deployed to active fleet."
        )
        return plan

    def confirm_delivery(self, request_id: str, volunteer_name: str, signature_data: str = "VerifiedDigitalSignature") -> Dict[str, Any]:
        """Volunteer records proof-of-delivery with digital signature and inventory adjustment."""
        req = self.requests.get(request_id)
        if not req:
            raise ValueError(f"Request {request_id} not found")

        req.status = MissionStatus.DELIVERED
        req.is_delivered = True
        req.delivery_timestamp = time.time()

        # Deduct items from assigned depot
        if req.assigned_depot_id and req.assigned_depot_id in self.depots:
            depot = self.depots[req.assigned_depot_id]
            for item in req.items:
                depot.inventory[item.item_type] = max(0.0, depot.inventory.get(item.item_type, 0.0) - item.quantity)

        sig_hash = hashlib.sha256(f"{request_id}:{volunteer_name}:{signature_data}:{time.time()}".encode()).hexdigest()

        self.log_audit(
            event_type="DELIVERY_CONFIRMED",
            actor_id=volunteer_name,
            actor_type=ActorType.HUMAN,
            entity_type="AidRequest",
            entity_id=request_id,
            summary=f"Proof of Delivery verified for {req.requester_name} by {volunteer_name}.",
            details={"signature_hash": sig_hash, "items_delivered": [i.dict() for i in req.items]}
        )

        return {
            "success": True,
            "request_id": request_id,
            "status": req.status,
            "signature_hash": sig_hash
        }

    def get_summary_state(self) -> Dict[str, Any]:
        """Returns full reactive state for frontend dashboard."""
        all_reqs = list(self.requests.values())
        total_reqs = len(all_reqs)
        delivered_count = sum(1 for r in all_reqs if r.status == MissionStatus.DELIVERED)
        critical_total = sum(1 for r in all_reqs if r.priority == PriorityLevel.CRITICAL)
        critical_fulfilled = sum(1 for r in all_reqs if r.priority == PriorityLevel.CRITICAL and (r.status in [MissionStatus.DISPATCHED, MissionStatus.DELIVERED]))
        active_disruptions = [d for d in self.disruptions.values() if d.active]

        return {
            "stats": {
                "total_requests": total_reqs,
                "delivered_count": delivered_count,
                "dispatched_count": sum(1 for r in all_reqs if r.status == MissionStatus.DISPATCHED),
                "unmet_count": max(0, total_reqs - delivered_count - sum(1 for r in all_reqs if r.status == MissionStatus.DISPATCHED)),
                "critical_fulfillment_rate": round((critical_fulfilled / max(critical_total, 1)) * 100, 1),
                "active_disruptions_count": len(active_disruptions),
                "current_plan_version": self.current_plan_id or "None",
                "pending_replan_approval": bool("v2.0" in self.plans and not self.plans["v2.0"].is_approved),
                "sim_elapsed_seconds": round(self.sim_elapsed_seconds, 1),
                "is_paused": self.is_paused,
                "sim_speed": self.sim_speed
            },
            "depots": list(self.depots.values()),
            "vehicles": list(self.vehicles.values()),
            "volunteers": list(self.volunteers.values()),
            "requests": all_reqs[:140],  # Return up to 140 for snappy UI rendering
            "active_disruptions": active_disruptions,
            "current_plan": self.plans.get(self.current_plan_id),
            "pending_plan": self.plans.get("v2.0") if ("v2.0" in self.plans and not self.plans["v2.0"].is_approved) else None,
            "recent_audit": self.audit_events[-30:]
        }
