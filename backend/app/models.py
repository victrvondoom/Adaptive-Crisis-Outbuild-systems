"""
AIDNEXUS ONE — Pydantic Data Models
Authoritative schemas for entities, optimizer requests, and state machine transitions.
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import uuid
import time

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
    urgency_score: float = 75.0
    duplicate_of_id: Optional[str] = None

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
    vehicle_type: str  # "Heavy 4x4 Cargo", "Amphibious Rescue Truck", "Medical Evac Van", "Drone Carrier"
    capacity_kg: float
    current_load_kg: float = 0.0
    base_depot_id: str
    current_lat: float
    current_lng: float
    status: str = "IDLE"  # IDLE, EN_ROUTE, DELIVERING, RETURNING, BROKEN_DOWN
    assigned_mission_ids: List[str] = []
    speed_kmh: float = 45.0
    route_waypoints: List[List[float]] = []  # [ [lat, lng], ... ]
    current_waypoint_idx: int = 0
    target_request_id: Optional[str] = None
    distance_traveled_km: float = 0.0
    fuel_pct: float = 100.0

class Volunteer(BaseModel):
    id: str
    name: str
    role: str  # "Paramedic Lead", "Logistics Driver", "Disaster Specialist"
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
    hazard_radius_km: float = 3.5

class PlanAssignment(BaseModel):
    vehicle_id: str
    depot_id: str
    request_ids: List[str]
    route_latlngs: List[List[float]] = []
    total_distance_km: float = 0.0
    estimated_duration_min: float = 0.0
    payload_weight_kg: float = 0.0

class MissionPlanVersion(BaseModel):
    version_id: str = "v1.0"
    created_at: float = Field(default_factory=time.time)
    created_by: str = "Agent 2: Resource Strategist"
    is_active: bool = False
    is_approved: bool = False
    approved_by: Optional[str] = None
    assignments: List[PlanAssignment] = []
    unmet_request_ids: List[str] = []
    total_distance_km: float = 0.0
    total_fulfilled: int = 0
    tradeoff_explanation: str = ""
    checksum: str = ""
    replan_delta: Dict[str, Any] = {}

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
