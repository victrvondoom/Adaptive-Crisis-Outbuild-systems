"""
AIDNEXUS ONE — FastAPI Backend Service
Authoritative Mission-Control REST API for dynamic optimization, disruption injection,
state transitions, and evidence verification.
"""
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .state_engine import CrisisStateEngine
from .models import DisruptionType, MissionStatus, ActorType
from .benchmark import run_comparative_benchmark

app = FastAPI(
    title="AIDNEXUS ONE Mission Control API",
    version="1.0.0",
    description="The Self-Healing Humanitarian Network API for OutSystems Hackathon 2026"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton simulation state
state_engine = CrisisStateEngine(seed=42)

# Request schemas for endpoints
class DisruptionPayload(BaseModel):
    type: DisruptionType
    title: str
    description: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    depot_id: Optional[str] = None

class TriagePayload(BaseModel):
    raw_text: str
    requester: Optional[str] = "Disaster Shelter Lead"
    lat: Optional[float] = 14.5995
    lng: Optional[float] = 120.9842
    sector: Optional[str] = "Central Metro"

class DeliveryPayload(BaseModel):
    request_id: str
    volunteer_name: str
    signature_data: Optional[str] = "DigitalTouchSignatureVerified"

class TransitionPayload(BaseModel):
    request_id: str
    new_status: MissionStatus
    actor_id: str
    actor_role: str = "MISSION_COORDINATOR"
    reason: Optional[str] = None

class ApprovalPayload(BaseModel):
    approver_name: Optional[str] = "Commander Elena Vance (Lead Coordinator)"

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
        "sim_time": state_engine.sim_elapsed_seconds
    }

@app.get("/api/v1/state")
def get_state():
    return state_engine.get_summary_state()

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
    result = state_engine.inject_disruption(
        dtype=payload.type,
        title=payload.title,
        description=payload.description,
        lat=payload.lat,
        lng=payload.lng,
        depot_id=payload.depot_id
    )
    return {
        "success": True,
        "disruption": result["disruption"],
        "assessment": result["assessment"],
        "replan_version": result["replan"].version_id,
        "replan_explanation": result["replan"].tradeoff_explanation,
        "replan_delta": result["replan"].replan_delta
    }

@app.post("/api/v1/replan/approve")
def approve_replan(payload: ApprovalPayload):
    try:
        plan = state_engine.approve_replan(approver_name=payload.approver_name or "Mission Coordinator")
        return {"success": True, "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/nlp/triage")
@app.post("/api/v1/triage")
def triage_aid_request(payload: TriagePayload):
    req = state_engine.agent1.triage_message(
        raw_text=payload.raw_text,
        requester=payload.requester or "Field Dispatch Emergency",
        lat=payload.lat or 14.5995,
        lng=payload.lng or 120.9842,
        sector=payload.sector or "Central Metro"
    )
    state_engine.requests[req.id] = req
    state_engine.log_audit(
        event_type="REQUEST_TRIAGED",
        actor_id="AGENT-01-NEED",
        actor_type=ActorType.AGENT,
        entity_type="AidRequest",
        entity_id=req.id,
        summary=f"Parsed request from {req.requester_name}: {len(req.items)} items extracted with {req.priority.value} priority."
    )
    return {"success": True, "request": req}

@app.post("/api/v1/deliveries/confirm")
def confirm_delivery(payload: DeliveryPayload):
    try:
        res = state_engine.confirm_delivery(
            request_id=payload.request_id,
            volunteer_name=payload.volunteer_name,
            signature_data=payload.signature_data or "DigitalSignature"
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/benchmark/run")
def run_benchmark(seed: int = 42):
    res = run_comparative_benchmark(seed=seed)
    return res

@app.post("/api/v1/missions/transition")
def transition_mission(payload: TransitionPayload):
    req = state_engine.requests.get(payload.request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    old_status = req.status
    req.status = payload.new_status
    if payload.new_status == MissionStatus.DELIVERED:
        req.is_delivered = True

    state_engine.log_audit(
        event_type="STATE_TRANSITION",
        actor_id=payload.actor_id,
        actor_type=ActorType.HUMAN,
        entity_type="AidRequest",
        entity_id=payload.request_id,
        summary=f"Transitioned mission from {old_status.value} to {payload.new_status.value}. Reason: {payload.reason or 'User action'}"
    )
    return {"success": True, "request_id": payload.request_id, "new_status": payload.new_status}

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
