"""
AIDNEXUS ONE — FastAPI Backend Service
Authoritative Mission-Control REST API for dynamic optimization, disruption
injection, state transitions, and evidence verification.

Security posture (honest): this is a single-tenant local demonstration system
with NO authentication. Every mutating endpoint is documented as such; the
production design (docs/security-model.md, OutSystems specs) places
authentication/authorization in the ODC application layer, which is not part of
this codebase.
"""
import os
import re
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .state_engine import CrisisStateEngine
from .models import DisruptionType, MissionStatus, ActorType, ALLOWED_TRANSITIONS
from .benchmark import run_comparative_benchmark, run_single_benchmark

app = FastAPI(
    title="AIDNEXUS ONE Mission Control API",
    version="2.0.0",
    description="The Self-Healing Humanitarian Network API for OutSystems Hackathon 2026"
)

# Same-origin serving: the frontend is served by this app, so a permissive
# cross-origin policy is unnecessary. Restrict to local development origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton simulation state
state_engine = CrisisStateEngine(seed=42)

# Basic input hardening for free-text fields (defense in depth; the frontend
# also escapes on render — see frontend/js/app.js escapeHtml).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _clean_text(value: str, max_len: int = 300) -> str:
    return _CONTROL_CHARS.sub("", value)[:max_len]


class DisruptionPayload(BaseModel):
    type: DisruptionType
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    lat: Optional[float] = None
    lng: Optional[float] = None
    depot_id: Optional[str] = None
    hazard_radius_km: float = Field(default=3.5, ge=0.1, le=50.0)

    @field_validator("title", "description")
    @classmethod
    def strip_control(cls, v: str) -> str:
        return _clean_text(v)


class TriagePayload(BaseModel):
    raw_text: str = Field(..., max_length=4000)
    requester: Optional[str] = Field(default="Disaster Shelter Lead", max_length=200)
    lat: Optional[float] = 14.5995
    lng: Optional[float] = 120.9842
    sector: Optional[str] = Field(default="Central Metro", max_length=100)

    @field_validator("raw_text", "requester", "sector")
    @classmethod
    def strip_control(cls, v: str) -> str:
        return _CONTROL_CHARS.sub("", v)


class DeliveryPayload(BaseModel):
    request_id: str = Field(..., max_length=64)
    volunteer_name: str = Field(..., max_length=200)
    signature_data: Optional[str] = Field(default="DigitalSignature", max_length=200)


class TransitionPayload(BaseModel):
    request_id: str = Field(..., max_length=64)
    new_status: MissionStatus
    actor_id: str = Field(..., max_length=200)
    actor_role: str = Field(default="MISSION_COORDINATOR", max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("actor_id", "reason")
    @classmethod
    def strip_control(cls, v):
        return _clean_text(v) if v else v


class ApprovalPayload(BaseModel):
    approver_name: Optional[str] = Field(default="Mission Coordinator", max_length=200)


class SimControlPayload(BaseModel):
    is_paused: Optional[bool] = None
    sim_speed: Optional[float] = None
    step_delta_sec: Optional[float] = 1.0


@app.get("/favicon.ico")
def get_favicon():
    return Response(status_code=204)


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "AIDNEXUS ONE Core Engine",
        "active_plan": state_engine.current_plan_id,
        "total_requests": len(state_engine.requests),
        "depots_count": len(state_engine.depots),
        "sim_time": state_engine.sim_elapsed_seconds,
        "queue_concordance": state_engine.queue_concordance(),
    }


@app.get("/api/v1/state")
def get_state():
    return state_engine.get_summary_state()


@app.get("/api/v1/dispatch-queue")
def get_dispatch_queue():
    """The authoritative dispatch queue: a projection of the active approved
    plan, ordered by the optimizer's scheduled_sequence."""
    return {"plan_version": state_engine.current_plan_id,
            "queue": state_engine.get_dispatch_queue(),
            "blocked": state_engine.get_blocked_requests(),
            "queue_concordance": state_engine.queue_concordance()}


@app.post("/api/v1/sim/tick")
def tick_simulation(payload: Optional[SimControlPayload] = None):
    dt = payload.step_delta_sec if (payload and payload.step_delta_sec) else 1.0
    res = state_engine.advance_simulation(delta_sec=dt)
    return res


@app.post("/api/v1/sim/control")
def control_simulation(payload: SimControlPayload):
    if payload.is_paused is not None:
        state_engine.is_paused = payload.is_paused
    if payload.sim_speed is not None:
        state_engine.sim_speed = max(0.25, min(payload.sim_speed, 10.0))
    return {
        "is_paused": state_engine.is_paused,
        "sim_speed": state_engine.sim_speed,
        "elapsed_seconds": state_engine.sim_elapsed_seconds
    }


@app.post("/api/v1/scenario/reset")
def reset_scenario(seed: int = 42):
    state_engine.reset_scenario(seed=seed)
    return {"success": True, "message": f"Scenario reset to clean baseline (seed={seed})."}


@app.post("/api/v1/disrupt")
def trigger_disruption(payload: DisruptionPayload):
    try:
        result = state_engine.inject_disruption(
            dtype=payload.type,
            title=payload.title,
            description=payload.description,
            lat=payload.lat,
            lng=payload.lng,
            depot_id=payload.depot_id,
            hazard_radius_km=payload.hazard_radius_km,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "success": True,
        "disruption": result["disruption"],
        "assessment":result["assessment"],
        "replan_version": result["replan"].version_id,
        "replan_explanation": result["replan"].tradeoff_explanation,
        "replan_delta": result["replan"].replan_delta,
        "agent_interpretation": result["interpretation"],
    }


@app.post("/api/v1/replan/approve")
def approve_replan(payload: ApprovalPayload):
    try:
        plan = state_engine.approve_pending_plan(
            approver_name=payload.approver_name or "Mission Coordinator")
        return {"success": True, "plan": plan.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/nlp/triage")
@app.post("/api/v1/triage")
def triage_aid_request(payload: TriagePayload):
    """Agent 1 full action: parse, classify, extract, duplicate-guard, sanitize.
    Returns the draft request plus the evidence object explaining every
    decision (no invented data — unparsed messages are flagged for review)."""
    req, evidence = state_engine.agent1.triage_message(
        raw_text=payload.raw_text,
        requester=payload.requester or "Field Dispatch Emergency",
        lat=payload.lat if payload.lat is not None else 14.5995,
        lng=payload.lng if payload.lng is not None else 120.9842,
        sector=payload.sector or "Central Metro",
        existing_requests=list(state_engine.requests.values()),
    )
    state_engine.requests[req.id] = req
    state_engine.log_audit(
        event_type="REQUEST_TRIAGED",
        actor_id="AGENT-01-NEED",
        actor_type=ActorType.AGENT,
        entity_type="AidRequest",
        entity_id=req.id,
        summary=(f"Parsed request from {req.requester_name}: {len(req.items)} items "
                 f"extracted with {req.priority.value} priority"
                 + ("; flagged for human review" if evidence["requires_human_review"] else "")),
        details={"evidence": evidence},
    )
    return {"success": True, "request": req.model_dump(), "evidence": evidence}


@app.post("/api/v1/deliveries/confirm")
def confirm_delivery(payload: DeliveryPayload):
    try:
        res = state_engine.confirm_delivery(
            request_id=payload.request_id,
            volunteer_name=payload.volunteer_name,
            signature_data=payload.signature_data or "DigitalSignature",
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/benchmark/run")
def run_benchmark(seed: int = 42, n_requests: int = 200):
    """Runs the REAL comparative simulation (FIFO / greedy / static / AIDNEXUS).
    All metrics are computed from the simulated execution trace."""
    if n_requests < 10 or n_requests > 1000:
        raise HTTPException(status_code=400, detail="n_requests must be in [10, 1000]")
    return run_single_benchmark(seed=seed, n_requests=n_requests)


@app.get("/api/v1/missions/{request_id}")
def get_mission(request_id: str):
    req = state_engine.requests.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    plan = state_engine.plans.get(state_engine.current_plan_id)
    entry = plan.request_entries.get(request_id) if plan else None
    return {"request": req.model_dump(),
            "plan_entry": entry.model_dump() if entry else None,
            "delivery_receipt": state_engine.delivery_receipts.get(request_id)}


@app.post("/api/v1/missions/transition")
def transition_mission(payload: TransitionPayload):
    """State-machine-validated transition. Illegal transitions are rejected
    with 400 + the list of allowed targets. DELIVERED must go through
    /deliveries/confirm so inventory and receipts are handled correctly."""
    try:
        res = state_engine.transition_mission(
            request_id=payload.request_id,
            new_status=payload.new_status,
            actor_id=payload.actor_id,
            reason=payload.reason,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Mount static directories directly so /css, /js, and /assets never 404
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    assets_dir = os.path.join(frontend_dir, "assets")

    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_frontend_root():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "Frontend ready at /static"}
