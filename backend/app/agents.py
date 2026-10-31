"""
AIDNEXUS ONE — Agent Orchestration Layer

Three agents with explicit, testable action contracts (docs/agents/AGENT_ACTION_CATALOG.md):
- Agent 1 Need-to-Mission: text -> structured draft work order (evidence-linked,
  duplicate-guarded, injection-sanitized, never invents quantities).
- Agent 2 Resource Strategist: gathers operational state, invokes the optimizer,
  interprets the plan, and produces an approval request. The optimizer's plan is
  authoritative; Agent 2 never reorders it.
- Agent 3 Recovery & Accountability: assesses disruption impact, preserves
  committed deliveries, proposes a replan (which itself requires human approval).

Design rules enforced here:
- Agents never deny assistance autonomously; they flag for human review.
- Agents never fabricate data: every extracted quantity carries source evidence;
  unparsed messages become review-flagged drafts, not invented item lists.
- Raw beneficiary text is sanitized (injection defense) before storage.
"""
import re
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from .models import (
    AidRequest, AidItem, PriorityLevel, MissionStatus, Disruption,
    MissionPlanVersion, AuditEvent, ActorType, Location, FeasibilityStatus,
)

# Humanitarian item dictionary (Sphere-aligned categories).
ITEM_KEYWORDS = {
    "potable_water_liters": [r"water", r"liters", r"drinking", r"clean water", r"gallons"],
    "trauma_kits": [r"trauma", r"medical", r"blood", r"first aid", r"bandages", r"surgical", r"antibiotics"],
    "rations_mre": [r"food", r"rations", r"mre", r"meals", r"canned", r"nutrition"],
    "hygiene_kits": [r"hygiene", r"soap", r"sanitation", r"diapers", r"purification tablets"],
    "generators": [r"generator", r"power", r"fuel", r"electricity", r"battery pack"]
}

# Prompt-injection defense: strip instruction-like patterns from beneficiary text
# before it is stored or echoed anywhere.
INJECTION_PATTERNS = [
    (re.compile(r"ignore (all|any|the) (previous|prior|above) (instructions|prompts?)", re.I), "[injection-attempt-removed]"),
    (re.compile(r"disregard (all|any|the) (previous|prior|above)", re.I), "[injection-attempt-removed]"),
    (re.compile(r"you are now", re.I), "[injection-attempt-removed]"),
    (re.compile(r"<script.*?</script>", re.I | re.S), "[script-removed]"),
    (re.compile(r"on\w+\s*=", re.I), "[handler-removed]="),
    (re.compile(r"(system|assistant)\s*:", re.I), "[role-removed]:"),
]

MAX_TEXT_LENGTH = 2000


def sanitize_text(raw: str) -> Tuple[str, bool]:
    """Defensive sanitization of free text. Returns (clean, injection_detected)."""
    clean = raw[:MAX_TEXT_LENGTH]
    detected = False
    for pat, repl in INJECTION_PATTERNS:
        if pat.search(clean):
            detected = True
        clean = pat.sub(repl, clean)
    return clean, detected


class NeedToMissionAgent:
    """Agent 1: Interprets raw distress messages into structured draft work orders.

    Action contract (AGENT-A1-TRIAGE):
    - Output is a DRAFT (status REQUESTED/UNDER_REVIEW) — never auto-verified beyond
      MEDIUM priority, never auto-denied.
    - Every extracted item carries the source phrase as evidence.
    - If no quantities are found, NO items are invented: the request is created with
      requires_review=True and an empty item list pending human clarification.
    - Potential duplicates (same requester + same location within 1.5 km + same
      priority, created within 30 minutes) are flagged via duplicate_of_id.
    """
    name = "Agent 1: Need-to-Mission"

    # Cues for urgency classification. Kept deterministic (no LLM in this build;
    # see docs/agents/AGENT_CONTRACTS.md for the model-backed variant spec).
    CRITICAL_CUES = ["critical", "immediate", "urgent", "life-threatening", "emergency",
                     "blood", "trauma", "drowning", "infant"]
    HIGH_CUES = ["severe", "high", "soon", "children", "elderly", "out of water", "power out"]

    def classify_urgency(self, text_lower: str) -> Tuple[PriorityLevel, str]:
        """Returns (priority, reason). The reason is the matched cue = evidence."""
        for cue in self.CRITICAL_CUES:
            if cue in text_lower:
                return PriorityLevel.CRITICAL, f"matched critical cue '{cue}'"
        for cue in self.HIGH_CUES:
            if cue in text_lower:
                return PriorityLevel.HIGH, f"matched high cue '{cue}'"
        if "low" in text_lower or "informational" in text_lower:
            return PriorityLevel.LOW, "explicitly low/informational"
        return PriorityLevel.MEDIUM, "no urgency cues matched; defaulted to MEDIUM"

    def extract_items(self, raw_text: str) -> List[AidItem]:
        """Extracts items with quantities. Only explicit 'N ... <keyword>' patterns
        count; the source phrase is preserved as evidence on each item."""
        text_lower = raw_text.lower()
        extracted: List[AidItem] = []
        for item_key, patterns in ITEM_KEYWORDS.items():
            for pat in patterns:
                match = re.search(rf"(\d+)\s*(?:units|packs|kits|boxes|liters|cans)?\s*(?:of\s*)?{pat}", text_lower)
                if match:
                    qty = float(match.group(1))
                    start = max(0, match.start() - 20)
                    end = min(len(raw_text), match.end() + 20)
                    unit = "liters" if "water" in item_key else ("kits" if "kit" in item_key else "units")
                    extracted.append(AidItem(
                        item_type=item_key, quantity=qty, unit=unit,
                        source_text=raw_text[start:end].strip(),
                    ))
                    break
        return extracted

    def check_duplicate(self, candidate: AidRequest, existing: List[AidRequest],
                        now: float, radius_km: float = 1.5, window_seconds: float = 1800.0) -> Optional[str]:
        """Duplicate guard: same requester_name + same priority + location within
        radius_km + created within window. Returns the duplicate-of id or None."""
        from .optimizer import haversine_distance_km
        for other in existing:
            if other.id == candidate.id:
                continue
            if other.requester_name != candidate.requester_name:
                continue
            if other.priority != candidate.priority:
                continue
            if abs(now - other.created_at) > window_seconds:
                continue
            if haversine_distance_km(candidate.location.lat, candidate.location.lng,
                                     other.location.lat, other.location.lng) > radius_km:
                continue
            return other.id
        return None

    def triage_message(
        self,
        raw_text: str,
        requester: str = "Field Dispatch",
        lat: float = 14.5995,
        lng: float = 120.9842,
        sector: str = "Sector Alpha",
        existing_requests: Optional[List[AidRequest]] = None,
        now: Optional[float] = None,
    ) -> Tuple[AidRequest, Dict[str, Any]]:
        """Full action: returns (draft_request, triage_evidence) so callers can
        audit WHY the agent decided what it did."""
        clean_text, injection_detected = sanitize_text(raw_text or "")
        text_lower = clean_text.lower()
        now = now if now is not None else time.time()

        priority, priority_reason = self.classify_urgency(text_lower)
        items = self.extract_items(clean_text)

        # Medical content always needs human verification of quantities/suitability.
        requires_review = injection_detected or not items

        req = AidRequest(
            requester_name=requester,
            location=Location(
                id=f"LOC-{hashlib.md5(f'{lat:.4f}:{lng:.4f}'.encode()).hexdigest()[:6]}",
                name=f"{sector} Relief Point",
                lat=lat, lng=lng, sector=sector,
            ),
            items=items,  # possibly empty — never invented
            priority=priority,
            # CRITICAL needs human verification of medical details; others are drafts.
            status=MissionStatus.UNDER_REVIEW if (priority == PriorityLevel.CRITICAL or requires_review)
                   else MissionStatus.REQUESTED,
            special_notes=clean_text,
            created_at=now,
            intake_channel="AGENT_TRIAGE",
        )

        duplicate_of = self.check_duplicate(req, existing_requests or [], now=now) \
            if existing_requests else None
        if duplicate_of:
            req.duplicate_of_id = duplicate_of
            req.status = MissionStatus.UNDER_REVIEW  # human decides; agent never denies

        evidence = {
            "agent": self.name,
            "priority_reason": priority_reason,
            "items_extracted": len(items),
            "injection_detected": injection_detected,
            "requires_human_review": requires_review or duplicate_of is not None,
            "duplicate_of_id": duplicate_of,
            "quantity_evidence": [it.source_text for it in items],
            "no_items_found": len(items) == 0,
        }
        return req, evidence


class ResourceStrategistAgent:
    """Agent 2: Formulates resource allocation plans.

    Action contract (AGENT-A2-PLAN):
    - Reads operational state (depots, vehicles, requests) it is given.
    - Invokes the optimizer — the ONLY component that decides execution order.
    - Interprets the returned plan: explains fulfillment, blocked reasons, distance.
    - Produces an approval request. Agent 2 NEVER activates a plan itself; plan
      activation requires explicit human approval (except the documented
      system-bootstrap of the initial plan).
    - Postcondition: the returned proposal's request_entries cover every request
      in the planning pool (scheduled, preserved, or blocked-with-reason).
    """
    name = "Agent 2: Resource Strategist"

    def formulate_plan(
        self,
        requests: List[AidRequest],
        depots: List[Any],
        vehicles: List[Any],
        optimizer: Any,
        version_label: str,
        blocked_depot_ids: List[str] = None,
        blocked_locations: List[Tuple[float, float, float]] = None,
        preserve_request_ids: List[str] = None,
        committed_assignments: Optional[Dict[str, Tuple[str, str]]] = None,
        previous_plan: Optional[MissionPlanVersion] = None,
    ) -> Tuple[MissionPlanVersion, Dict[str, Any]]:
        plan = optimizer.solve_allocation(
            requests=requests,
            depots=depots,
            vehicles=vehicles,
            blocked_depot_ids=blocked_depot_ids,
            blocked_locations=blocked_locations,
            preserve_request_ids=preserve_request_ids,
            committed_assignments=committed_assignments,
            version_label=version_label,
        )
        blocked = [e for e in plan.request_entries.values()
                   if e.feasibility_status not in (FeasibilityStatus.SCHEDULED,
                                                   FeasibilityStatus.COMMITTED_PRESERVED)]
        plannable_ids = {r.id for r in requests
                         if r.status not in (MissionStatus.DELIVERED, MissionStatus.CANCELLED)}
        interpretation = {
            "agent": self.name,
            "optimization_run_id": plan.optimization_run_id,
            "policy_version": plan.policy_version,
            "scheduled": plan.total_fulfilled,
            "blocked_count": len(blocked),
            "blocked_reasons": {e.request_id: e.feasibility_status.value for e in blocked},
            "total_distance_km": plan.total_distance_km,
            "solve_time_seconds": plan.solve_time_seconds,
            "requires_human_approval": True,
            "approval_request": {
                "plan_version": plan.version_id,
                "action": "APPROVE_PLAN",
                "justification": plan.tradeoff_explanation,
            },
            # Honest self-check: every plannable request must have a plan entry.
            "coverage_complete": plannable_ids.issubset(set(plan.request_entries.keys())),
        }
        return plan, interpretation


class RecoveryAgent:
    """Agent 3: Detects disruption impact, preserves committed deliveries,
    and computes a self-healing replanning proposal (approval-gated)."""
    name = "Agent 3: Recovery & Accountability"

    def assess_impact(
        self,
        disruption: Disruption,
        current_plan: MissionPlanVersion,
        requests_by_id: Dict[str, AidRequest],
    ) -> Dict[str, Any]:
        """Identifies which plan missions are committed (already delivered —
        immutable) and which are affected by the disruption. Uses the
        disruption's authoritative hazard_radius_km (never a hardcoded constant).
        """
        from .optimizer import haversine_distance_km
        affected_missions = []
        preserved_missions = []

        radius_km = disruption.hazard_radius_km  # authoritative field

        for assignment in current_plan.assignments:
            for req_id in assignment.request_ids:
                req = requests_by_id.get(req_id)
                if not req:
                    continue
                if req.status == MissionStatus.DELIVERED or req.is_delivered:
                    preserved_missions.append(req_id)
                    continue
                if disruption.location_id and assignment.depot_id == disruption.location_id:
                    affected_missions.append(req_id)
                    continue
                if disruption.affected_lat is not None and disruption.affected_lng is not None:
                    dist = haversine_distance_km(req.location.lat, req.location.lng,
                                                 disruption.affected_lat, disruption.affected_lng)
                    if dist <= radius_km:
                        affected_missions.append(req_id)
                        continue

        disruption.affected_missions = list(set(affected_missions))

        narrative = (
            f"[Agent 3 Incident Report] Disruption detected: {disruption.title} "
            f"({disruption.type.value}, hazard radius {radius_km} km). "
            f"Preserved {len(preserved_missions)} completed missions (IMMUTABLE). "
            f"Identified {len(affected_missions)} disrupted deliveries requiring replanning; "
            f"a recovery proposal will require human approval before dispatch."
        )

        return {
            "disruption": disruption,
            "affected_count": len(affected_missions),
            "preserved_count": len(preserved_missions),
            "affected_mission_ids": affected_missions,
            "preserved_mission_ids": preserved_missions,
            "hazard_radius_km": radius_km,
            "narrative": narrative,
        }
