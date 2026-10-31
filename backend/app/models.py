"""
AIDNEXUS ONE — Pydantic Data Models
Authoritative schemas for entities, optimizer requests, and state machine transitions.

Canonical plan data contract (see docs/context/DOMAIN_MODEL.md):
- MissionPlanVersion is the single source of truth for execution order.
- Every scheduled request has a PlannedRequestEntry with humanitarian priority
  (policy) AND operational schedule (solver output). The UI renders projections
  of these entries and must never recompute or reorder them.
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import uuid
import time

# Humanitarian priority policy version. Bump when PRIORITY_WEIGHTS or the
# scoring rules change. Agents and the optimizer must report this version.
POLICY_VERSION = "policy-2026-11-v1"

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class MissionStatus(str, Enum):
    REQUESTED = "REQUESTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    PLANNED = "PLANNED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    REPLAN_PENDING = "REPLAN_PENDING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# Authoritative state machine: mission status transitions.
# Terminal states have no outgoing edges. Any other transition must be rejected.
ALLOWED_TRANSITIONS: Dict[MissionStatus, List[MissionStatus]] = {
    MissionStatus.REQUESTED: [MissionStatus.UNDER_REVIEW, MissionStatus.VERIFIED, MissionStatus.CANCELLED],
    MissionStatus.UNDER_REVIEW: [MissionStatus.VERIFIED, MissionStatus.REQUESTED, MissionStatus.CANCELLED],
    MissionStatus.VERIFIED: [MissionStatus.PLANNED, MissionStatus.CANCELLED],
    MissionStatus.PLANNED: [MissionStatus.PENDING_APPROVAL, MissionStatus.VERIFIED, MissionStatus.CANCELLED],
    MissionStatus.PENDING_APPROVAL: [MissionStatus.APPROVED, MissionStatus.PLANNED, MissionStatus.CANCELLED],
    MissionStatus.APPROVED: [MissionStatus.DISPATCHED, MissionStatus.CANCELLED],
    MissionStatus.DISPATCHED: [MissionStatus.IN_TRANSIT, MissionStatus.ARRIVED, MissionStatus.DELIVERED,
                               MissionStatus.REPLAN_PENDING, MissionStatus.CANCELLED, MissionStatus.FAILED],
    MissionStatus.IN_TRANSIT: [MissionStatus.ARRIVED, MissionStatus.DELIVERED, MissionStatus.FAILED,
                               MissionStatus.REPLAN_PENDING],
    MissionStatus.ARRIVED: [MissionStatus.DELIVERED, MissionStatus.FAILED],
    MissionStatus.REPLAN_PENDING: [MissionStatus.DISPATCHED, MissionStatus.VERIFIED, MissionStatus.CANCELLED],
    MissionStatus.DELIVERED: [],   # terminal: a confirmed delivery is immutable
    MissionStatus.CANCELLED: [],   # terminal
    MissionStatus.FAILED: [MissionStatus.VERIFIED, MissionStatus.CANCELLED],
}

class DisruptionType(str, Enum):
    ROAD_BLOCKAGE = "ROAD_BLOCKAGE"
    DEPOT_OUTAGE = "DEPOT_OUTAGE"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    WEATHER_HAZARD = "WEATHER_HAZARD"

class ActorType(str, Enum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"

class Location(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    sector: str = "Central"

class AidItem(BaseModel):
    item_type: str  # "potable_water_liters", "trauma_kits", "rations_mre", "hygiene_kits", "generators"
    quantity: float
    unit: str
    # Evidence: the source phrase this item was extracted from (Agent 1 contract).
    source_text: Optional[str] = None

class AidRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    requester_name: str
    location: Location
    items: List[AidItem]
    priority: PriorityLevel
    status: MissionStatus = MissionStatus.REQUESTED
    created_at: float = Field(default_factory=time.time)
    deadline_hours: float = 24.0
    affected_people: int = 10
    special_notes: Optional[str] = None
    assigned_vehicle_id: Optional[str] = None
    assigned_depot_id: Optional[str] = None
    assigned_volunteer_id: Optional[str] = None
    estimated_arrival_minutes: Optional[float] = None
    is_delivered: bool = False
    delivery_timestamp: Optional[float] = None
    # Humanitarian priority score under the canonical policy (see optimizer.PRIORITY_WEIGHTS).
    urgency_score: float = 75.0
    duplicate_of_id: Optional[str] = None
    # Provenance: how this request entered the system (SEED_SCENARIO | AGENT_TRIAGE | MANUAL).
    intake_channel: str = "MANUAL"

class Depot(BaseModel):
    id: str
    name: str
    location: Location
    inventory: Dict[str, float]  # item_type -> available quantity
    status: str = "OPERATIONAL"  # OPERATIONAL, FLOODED, DAMAGED
    capacity_sqm: float = 2500.0

class Vehicle(BaseModel):
    id: str
    name: str
    vehicle_type: str  # "Heavy 4x4 Cargo", "Amphibious Rescue Truck", "Medical Evac Van", "Rapid Response Carrier"
    capacity_kg: float
    current_load_kg: float = 0.0
    base_depot_id: str
    current_lat: float
    current_lng: float
    status: str = "IDLE"  # IDLE, EN_ROUTE, DELIVERING, RETURNING, BROKEN_DOWN
    assigned_mission_ids: List[str] = []
    assigned_volunteer_id: Optional[str] = None
    speed_kmh: float = 45.0
    route_waypoints: List[List[float]] = []  # [ [lat, lng], ... ]
    current_waypoint_idx: int = 0
    target_request_id: Optional[str] = None
    distance_traveled_km: float = 0.0
    fuel_pct: float = 100.0

class Volunteer(BaseModel):
    id: str
    name: str
    role: str  # "Paramedic Lead", "Emergency Nurse", "Heavy Logistics Driver", "Disaster Specialist"
    status: str = "AVAILABLE"  # AVAILABLE, ASSIGNED, RESTING
    assigned_vehicle_id: Optional[str] = None
    phone: str = "+1-555-AID-019"

class Disruption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: DisruptionType
    title: str
    description: str
    location_id: Optional[str] = None
    affected_lat: Optional[float] = None
    affected_lng: Optional[float] = None
    severity: str = "CRITICAL"  # MINOR, MODERATE, SEVERE, CRITICAL
    active: bool = True
    detected_at: float = Field(default_factory=time.time)
    affected_missions: List[str] = []
    # Authoritative hazard radius in km. Consumers (Agent 3, optimizer, UI map)
    # must read this field, never a hardcoded constant.
    hazard_radius_km: float = 3.5

class FeasibilityStatus(str, Enum):
    """Why a request is (not) scheduled in a plan. Blocking statuses are shown
    in the UI blocked-requests section with their reason — never hidden."""
    SCHEDULED = "SCHEDULED"
    COMMITTED_PRESERVED = "COMMITTED_PRESERVED"      # already dispatched/delivered, untouched by replan
    BLOCKED_HAZARD = "BLOCKED_HAZARD"                # request location inside active hazard zone
    BLOCKED_NO_STOCK = "BLOCKED_NO_STOCK"            # no operational depot holds requested items
    BLOCKED_NO_CAPACITY = "BLOCKED_NO_CAPACITY"      # no vehicle with remaining capacity
    DEADLINE_INFEASIBLE = "DEADLINE_INFEASIBLE"      # earliest feasible arrival exceeds deadline
    NOT_PLANNED = "NOT_PLANNED"                      # request not yet in planning pool (e.g. REQUESTED)

class PlannedRequestEntry(BaseModel):
    """The per-request plan data contract (Part 6). One entry per request per
    plan version. The dispatch queue is a projection of these entries."""
    request_id: str
    assignment_id: str            # "<plan_version>/<vehicle_id>"
    humanitarian_priority: str    # PriorityLevel value under POLICY_VERSION
    urgency_score: float          # canonical policy score
    scheduled_sequence: int       # position in the plan-wide execution order (1-based)
    scheduled_start_min: float    # minutes after plan start when the vehicle leaves depot
    estimated_arrival_min: float  # estimated arrival at this request (minutes after plan start)
    assigned_depot: Optional[str] = None
    assigned_vehicle: Optional[str] = None
    assigned_volunteer: Optional[str] = None
    feasibility_status: FeasibilityStatus
    unmet_demand: Dict[str, float] = {}   # item_type -> unmet quantity (normally empty)
    explanation_reference: str = ""       # pointer to human-readable explanation

class PlanAssignment(BaseModel):
    vehicle_id: str
    depot_id: str
    request_ids: List[str]
    route_latlngs: List[List[float]] = []
    total_distance_km: float = 0.0
    estimated_duration_min: float = 0.0
    payload_weight_kg: float = 0.0
    assigned_volunteer_id: Optional[str] = None

class MissionPlanVersion(BaseModel):
    version_id: str = "v1.0"
    optimization_run_id: str = ""          # unique id of the solver invocation that produced this plan
    policy_version: str = POLICY_VERSION   # humanitarian priority policy used to build it
    created_at: float = Field(default_factory=time.time)
    created_by: str = "Agent 2: Resource Strategist"
    is_active: bool = False
    is_approved: bool = False
    approved_by: Optional[str] = None
    # True only when approval was granted by the system bootstrap (initial plan),
    # so the UI can label it honestly instead of implying a human clicked it.
    auto_approved: bool = False
    assignments: List[PlanAssignment] = []
    request_entries: Dict[str, PlannedRequestEntry] = {}  # request_id -> entry
    unmet_request_ids: List[str] = []
    total_distance_km: float = 0.0
    total_fulfilled: int = 0
    tradeoff_explanation: str = ""
    checksum: str = ""
    replan_delta: Dict[str, Any] = {}
    solve_time_seconds: float = 0.0

class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = Field(default_factory=time.time)
    event_type: str
    actor_id: str
    actor_type: ActorType
    entity_type: str
    entity_id: str
    summary: str
    details: Dict[str, Any] = {}
    sha256_hash: str = ""
    prev_hash: str = ""   # hash chain: hash of the previous event ("" for genesis)

class BenchmarkMetric(BaseModel):
    strategy_name: str
    fulfilled_count: int
    critical_fulfilled_pct: float
    total_travel_km: float
    avg_delivery_time_min: float
    unmet_demand_count: int
    disruption_resilience_score: float
    replan_latency_seconds: float
    carbon_emission_kg: float
    # Integrity + comparability fields (computed, never fabricated)
    total_requests: int = 0
    critical_total: int = 0
    critical_fulfilled_count: int = 0
    on_time_delivery_pct: float = 0.0
    planning_time_seconds: float = 0.0
    inventory_violations: int = 0
    capacity_violations: int = 0
    duplicate_dispatches: int = 0
    affected_count: int = 0          # requests impacted by the disruption
    disruption_time_min: float = 0.0  # when the disruption struck (sim minutes)
