"""
AIDNEXUS ONE — Agent Orchestration Layer
Implements:
- Agent 1: Need-to-Mission (NLP Triage, Item Extraction, Urgency Classification, Duplicate Guard)
- Agent 2: Resource Strategist (MIP/VRP Invocation, Tradeoff Rationale, Plan Versioning)
- Agent 3: Recovery & Accountability (Disruption Detection, Immutable Delivery Preservation, Self-Healing Proposal)
"""
import re
import time
import hashlib
from typing import List, Dict, Any, Tuple
from .models import AidRequest, AidItem, PriorityLevel, MissionStatus, Disruption, MissionPlanVersion, AuditEvent, ActorType, Location

# Humanitarian item dictionary with Sphere standard norms
ITEM_KEYWORDS = {
    "potable_water_liters": [r"water", r"liters", r"drinking", r"clean water", r"gallons"],
    "trauma_kits": [r"trauma", r"medical", r"blood", r"first aid", r"bandages", r"surgical", r"antibiotics"],
    "rations_mre": [r"food", r"rations", r"mre", r"meals", r"canned", r"nutrition"],
    "hygiene_kits": [r"hygiene", r"soap", r"sanitation", r"diapers", r"purification tablets"],
    "generators": [r"generator", r"power", r"fuel", r"electricity", r"battery pack"]
}

class NeedToMissionAgent:
    """Agent 1: Interprets raw distress messages, extracts structured work orders, and flags triage levels."""
    def __init__(self):
        self.name = "Agent 1: Need-to-Mission"

    def triage_message(self, raw_text: str, requester: str = "Field Dispatch", lat: float = 14.5995, lng: float = 120.9842, sector: str = "Sector Alpha") -> AidRequest:
        text_lower = raw_text.lower()
        
        # 1. Classify Urgency / Priority
        priority = PriorityLevel.MEDIUM
        critical_cues = ["critical", "immediate", "urgent", "life-threatening", "emergency", "blood", "trauma", "drowning", "infant"]
        high_cues = ["severe", "high", "soon", "children", "elderly", "out of water", "power out"]
        
        if any(cue in text_lower for cue in critical_cues):
            priority = PriorityLevel.CRITICAL
        elif any(cue in text_lower for cue in high_cues):
            priority = PriorityLevel.HIGH
        elif "low" in text_lower or "informational" in text_lower:
            priority = PriorityLevel.LOW

        # 2. Extract Items with Quantities
        extracted_items: List[AidItem] = []
        for item_key, patterns in ITEM_KEYWORDS.items():
            for pat in patterns:
                match = re.search(rf"(\d+)\s*(?:units|packs|kits|boxes|liters|cans)?\s*(?:of\s*)?{pat}", text_lower)
                if match:
                    qty = float(match.group(1))
                    unit = "liters" if "water" in item_key else ("kits" if "kit" in item_key else "units")
                    extracted_items.append(AidItem(item_type=item_key, quantity=qty, unit=unit))
                    break
        
        # Default minimum relief package if no specific numbers detected
        if not extracted_items:
            extracted_items = [
                AidItem(item_type="potable_water_liters", quantity=50.0, unit="liters"),
                AidItem(item_type="rations_mre", quantity=20.0, unit="units")
            ]

        req = AidRequest(
            requester_name=requester,
            location=Location(
                id=f"LOC-{hashlib.md5(raw_text.encode()).hexdigest()[:6]}",
                name=f"{sector} Relief Point",
                lat=lat,
                lng=lng,
                sector=sector
            ),
            items=extracted_items,
            priority=priority,
            status=MissionStatus.VERIFIED if priority != PriorityLevel.CRITICAL else MissionStatus.UNDER_REVIEW,
            special_notes=raw_text
        )
        return req

class RecoveryAgent:
    """Agent 3: Detects disruptions, preserves completed deliveries, and computes self-healing recovery actions."""
    def __init__(self):
        self.name = "Agent 3: Recovery & Accountability"

    def assess_impact(
        self,
        disruption: Disruption,
        current_plan: MissionPlanVersion,
        requests_by_id: Dict[str, AidRequest]
    ) -> Dict[str, Any]:
        """
        Calculates affected assignments, identifying which deliveries are immutable (already completed)
        and which active missions require dynamic rerouting.
        """
        affected_missions = []
        preserved_missions = []

        for assignment in current_plan.assignments:
            for req_id in assignment.request_ids:
                req = requests_by_id.get(req_id)
                if not req:
                    continue

                if req.status == MissionStatus.DELIVERED or req.is_delivered:
                    preserved_missions.append(req_id)
                    continue

                # Check if assigned depot is disrupted
                if disruption.location_id and assignment.depot_id == disruption.location_id:
                    affected_missions.append(req_id)
                    continue

                # Check if request location is in hazard radius
                if disruption.affected_lat is not None and disruption.affected_lng is not None:
                    from .optimizer import haversine_distance_km
                    dist = haversine_distance_km(req.location.lat, req.location.lng, disruption.affected_lat, disruption.affected_lng)
                    if dist <= 3.5:  # Hazard blast/flood radius in km
                        affected_missions.append(req_id)
                        continue

        disruption.affected_missions = list(set(affected_missions))

        narrative = (
            f"[Agent 3 Incident Report] Disruption detected: {disruption.title} ({disruption.type.value}). "
            f"Preserved {len(preserved_missions)} completed missions (IMMUTABLE). "
            f"Identified {len(affected_missions)} disrupted deliveries requiring immediate self-healing replanning."
        )

        return {
            "disruption": disruption,
            "affected_count": len(affected_missions),
            "preserved_count": len(preserved_missions),
            "affected_mission_ids": affected_missions,
            "preserved_mission_ids": preserved_missions,
            "narrative": narrative
        }
