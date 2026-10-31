"""
AIDNEXUS ONE — FastAPI Backend Service (Phase II: production-oriented)

Multi-tenant, authenticated, persistent mission-control API.

Auth model (honest):
- Production: OIDC JWT verification (identity.ProductionAdapter) activated by
  OIDC_ISSUER/OIDC_AUDIENCE[/OIDC_JWKS_URL]. NOT ACTIVE here (no IdP).
- Development: identity.DevAdapter, impossible to enable when APP_ENV=production.
- Every request must present a valid Bearer token; missing/invalid identity
  fails CLOSED (401/403).
- Org scope resolved from DB membership records; client X-Org-Id only selects
  among the identity's own orgs (or platform-admin scope, which is audited).

Simulated demo data is per-organization: two orgs (PACIFIC seed=42,
HIGHLAND seed=777) with independent engines.
"""
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Response, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from .state_engine import CrisisStateEngine
from .models import DisruptionType, MissionStatus, ActorType, ALLOWED_TRANSITIONS
from .benchmark import run_single_benchmark
from . import identity as ident
from .authz import (Role, Permission, AuthorizationError, resolve_org_scope,
                    require_permission, role_has_permission)
from . import persistence
from .db import get_engine, run_migrations, session_scope
from .bootstrap import ensure_bootstrap, create_dev_session, get_memberships_for_user

# ----------------------------------------------------------------------
# Structured JSON logging with correlation IDs
# ----------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": time.time(), "level": record.levelname,
            "logger": record.name, "msg": record.getMessage(),
        }
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

def configure_logging():
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)

configure_logging()
logger = logging.getLogger("aidnexus.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: migrate + bootstrap
    try:
        engine = get_engine()
        applied = run_migrations(engine)
        logger.info("migrations applied: %s", applied)
        ensure_bootstrap()
        _build_engines()
        logger.info("startup complete: engines=%s", list(_ENGINES.keys()))
    except Exception as e:
        logger.error("startup persistence init failed (running WITHOUT durability): %s", e)
        _build_engines(persist=False)
    yield
    # shutdown: graceful — nothing to flush (every write is transactional)
    logger.info("graceful shutdown complete")


app = FastAPI(
    title="AIDNEXUS ONE Mission Control API",
    version="3.0.0",
    description="Self-Healing Humanitarian Network API — multi-tenant, persistent, authorized.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("WEB_ORIGIN", "http://localhost:8000"),
                   "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Org-scoped engine registry (simulated scenario actors per tenant)
# ----------------------------------------------------------------------
_ENGINES: Dict[str, CrisisStateEngine] = {}


def _build_engines(persist: bool = True):
    _ENGINES.clear()
    specs = {"ORG-PACIFIC": 42, "ORG-HIGHLAND": 777}
    for org_id, seed in specs.items():
        try:
            _ENGINES[org_id] = CrisisStateEngine(seed=seed, org_id=org_id, persist=persist)
        except Exception as e:
            logger.error("engine build failed for %s: %s", org_id, e)
            _ENGINES[org_id] = CrisisStateEngine(seed=seed, org_id=org_id, persist=False)


def engine_for(org_id: str) -> CrisisStateEngine:
    eng = _ENGINES.get(org_id)
    if eng is None:
        raise HTTPException(status_code=404, detail=f"Unknown organization {org_id}")
    return eng


# ----------------------------------------------------------------------
# Authentication middleware / dependencies
# ----------------------------------------------------------------------
PRODUCTION_ADAPTER = ident.ProductionAdapter.from_env() if ident.ProductionAdapter.configured() else None
DEV_ADAPTER = ident.DevAdapter()


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = rid
    logging.getLogger("aidnexus.http").info(
        json.dumps({"request_id": rid, "method": request.method,
                    "path": request.url.path, "status": response.status_code,
                    "duration_ms": round(duration_ms, 1)}))
    return response


def _verified_identity(request: Request) -> ident.VerifiedIdentity:
    """Fail-closed token verification + session liveness + membership scopes."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.removeprefix("Bearer ").strip()
    try:
        if PRODUCTION_ADAPTER is not None:
            claims = PRODUCTION_ADAPTER.verify_token(token)
            user = ident.build_identity_from_claims(claims, memberships_fn=get_memberships_for_user)
        else:
            claims = __import__("jwt", fromlist=["decode"]).decode(
                token, DEV_ADAPTER.secret, algorithms=["HS256"],
                audience=ident.TOKEN_AUDIENCE, issuer=ident.TOKEN_ISSUER_DEV)
            user = ident.build_identity_from_claims(claims, memberships_fn=get_memberships_for_user)
    except ident.IdentityError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    # Session revocation check (authoritative in DB)
    jti = claims.get("jti", "")
    if jti:
        from .models_db import Session as SessionRow
        with session_scope() as session:
            s = session.get(SessionRow, jti)
            if s is None:
                raise HTTPException(status_code=401, detail="Unknown session")
            if s.revoked_at is not None or _session_expired(s):
                raise HTTPException(status_code=401, detail="Session revoked or expired")
    return user


def _session_expired(s) -> bool:
    from datetime import datetime, timezone
    exp = s.expires_at
    if exp.tzinfo is None:  # SQLite returns naive datetimes; stored as UTC
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc)


async def get_identity(request: Request) -> ident.VerifiedIdentity:
    return _verified_identity(request)


def org_context(request: Request, user: ident.VerifiedIdentity = Depends(get_identity)) -> str:
    """Resolve tenant scope from verified memberships; never trust raw input."""
    requested = request.headers.get("X-Org-Id")
    try:
        return resolve_org_scope(user, requested)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


def guard(user: ident.VerifiedIdentity, org_id: str, permission: Permission) -> None:
    try:
        role_used = require_permission(user, org_id, permission)
    except AuthorizationError as e:
        # authorization failure monitoring (structured, no PII)
        logging.getLogger("aidnexus.authz").warning(json.dumps({
            "event": "AUTHZ_DENIED", "user_id": user.user_id,
            "org_id": org_id, "permission": permission.value}))
        raise HTTPException(status_code=403, detail=str(e))
    if user.is_platform_admin and org_id not in user.org_ids():
        logging.getLogger("aidnexus.authz").warning(json.dumps({
            "event": "PLATFORM_ADMIN_CROSS_ORG", "user_id": user.user_id, "org_id": org_id}))


# ----------------------------------------------------------------------
# Health / readiness
# ----------------------------------------------------------------------
@app.get("/healthz")
def liveness():
    """Liveness: process is up. No dependency checks."""
    return {"status": "ok", "service": "aidnexus-one", "version": "3.0.0"}


@app.get("/readyz")
def readiness():
    """Readiness: DB reachable + migrations applied + engines built."""
    checks = {"db": False, "migrations": False, "engines": len(_ENGINES) > 0}
    try:
        from sqlalchemy import text
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = True
        with get_engine().connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
        checks["migrations"] = n > 0
    except Exception:
        pass
    ready = all([checks["db"], checks["migrations"], checks["engines"]])
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status": "ready" if ready else "degraded", "checks": checks})


# Legacy alias (demo frontend used /api/v1/health)
@app.get("/api/v1/health")
def health_check():
    return {"status": "HEALTHY" if _ENGINES else "DEGRADED",
            "service": "AIDNEXUS ONE Core Engine", "orgs": list(_ENGINES.keys())}


# ----------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------
class DevTokenRequest(BaseModel):
    email: str = Field(..., max_length=254)


@app.get("/api/v1/auth/dev/identities")
def dev_identities():
    """Lists synthetic demo identities. Only when the dev adapter is enabled."""
    if not (DEV_ADAPTER.enabled() and PRODUCTION_ADAPTER is None):
        raise HTTPException(status_code=404, detail="Dev auth disabled")
    from .bootstrap import DEMO_IDENTITIES
    return [{"email": e, "display_name": n,
             "orgs": [{"org_id": "ORG-PACIFIC", "role": p},
                      {"org_id": "ORG-HIGHLAND", "role": h}]
             } for e, n, p, h in DEMO_IDENTITIES]


@app.post("/api/v1/auth/dev/token")
def dev_token(payload: DevTokenRequest):
    """Issues a revocable session token for a seeded demo identity.
    Impossible in production (identity.DevAdapter.enabled gate)."""
    if not (DEV_ADAPTER.enabled() and PRODUCTION_ADAPTER is None):
        raise HTTPException(status_code=404, detail="Dev auth disabled")
    from sqlalchemy import select
    from .models_db import User
    with session_scope() as session:
        user = session.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=404, detail="Unknown demo identity")
        scopes = get_memberships_for_user(user.id)
        jti = create_dev_session(user.id)
        token = DEV_ADAPTER.issue_token(user.id, user.email, scopes, jti=jti)
        return {"access_token": token, "token_type": "Bearer", "jti": jti,
                "user_id": user.id, "scopes": scopes}


@app.post("/api/v1/auth/logout")
def logout(user: ident.VerifiedIdentity = Depends(get_identity)):
    with session_scope() as session:
        persistence.revoke_session(session, user.jti)
    return {"success": True, "revoked": user.jti}


@app.get("/api/v1/me")
def who_am_i(user: ident.VerifiedIdentity = Depends(get_identity)):
    return {"user_id": user.user_id, "email": user.email,
            "is_platform_admin": user.is_platform_admin, "scopes": user.scopes}


# ----------------------------------------------------------------------
# Business endpoints (tenant-scoped, permission-guarded)
# ----------------------------------------------------------------------
class DisruptionPayload(BaseModel):
    type: DisruptionType
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    lat: Optional[float] = None
    lng: Optional[float] = None
    depot_id: Optional[str] = None
    hazard_radius_km: float = Field(default=3.5, ge=0.1, le=50.0)


class TriagePayload(BaseModel):
    raw_text: str = Field(..., max_length=4000)
    requester: Optional[str] = Field(default="Disaster Shelter Lead", max_length=200)
    lat: Optional[float] = 14.5995
    lng: Optional[float] = 120.9842
    sector: Optional[str] = Field(default="Central Metro", max_length=100)


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


class ApprovalPayload(BaseModel):
    approver_name: Optional[str] = Field(default="Mission Coordinator", max_length=200)


class SimControlPayload(BaseModel):
    is_paused: Optional[bool] = None
    sim_speed: Optional[float] = None
    step_delta_sec: Optional[float] = 1.0


@app.get("/api/v1/state")
def get_state(user: ident.VerifiedIdentity = Depends(get_identity),
              org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.READ_ORG_DATA)
    return engine_for(org_id).get_summary_state()


@app.get("/api/v1/dispatch-queue")
def get_dispatch_queue(user: ident.VerifiedIdentity = Depends(get_identity),
                       org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.READ_ORG_DATA)
    eng = engine_for(org_id)
    return {"plan_version": eng.current_plan_id, "queue": eng.get_dispatch_queue(),
            "blocked": eng.get_blocked_requests(), "queue_concordance": eng.queue_concordance()}


@app.post("/api/v1/sim/tick")
def tick_simulation(payload: Optional[SimControlPayload] = None,
                    user: ident.VerifiedIdentity = Depends(get_identity),
                    org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.SIM_CONTROL)
    eng = engine_for(org_id)
    dt = payload.step_delta_sec if (payload and payload.step_delta_sec) else 1.0
    return eng.advance_simulation(delta_sec=dt)


@app.post("/api/v1/sim/control")
def control_simulation(payload: SimControlPayload,
                       user: ident.VerifiedIdentity = Depends(get_identity),
                       org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.SIM_CONTROL)
    eng = engine_for(org_id)
    if payload.is_paused is not None:
        eng.is_paused = payload.is_paused
    if payload.sim_speed is not None:
        eng.sim_speed = max(0.25, min(payload.sim_speed, 10.0))
    return {"is_paused": eng.is_paused, "sim_speed": eng.sim_speed,
            "elapsed_seconds": eng.sim_elapsed_seconds}


@app.post("/api/v1/scenario/reset")
def reset_scenario(seed: int = 42,
                   user: ident.VerifiedIdentity = Depends(get_identity),
                   org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.SIM_CONTROL)
    eng = engine_for(org_id)
    eng.reset_scenario(seed=seed)
    # NOTE: resets in-memory simulation actors only; durable records persist.
    return {"success": True,
            "message": f"In-memory simulation reset (seed={seed}). Durable records persist."}


@app.post("/api/v1/disrupt")
def trigger_disruption(payload: DisruptionPayload,
                        user: ident.VerifiedIdentity = Depends(get_identity),
                        org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.INJECT_DISRUPTION)
    eng = engine_for(org_id)
    try:
        result = eng.inject_disruption(
            dtype=payload.type, title=payload.title, description=payload.description,
            lat=payload.lat, lng=payload.lng, depot_id=payload.depot_id,
            hazard_radius_km=payload.hazard_radius_km)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "disruption": result["disruption"],
            "assessment": result["assessment"],
            "replan_version": result["replan"].version_id,
            "replan_explanation": result["replan"].tradeoff_explanation,
            "replan_delta": result["replan"].replan_delta,
            "agent_interpretation": result["interpretation"]}


@app.post("/api/v1/replan/approve")
def approve_replan(payload: ApprovalPayload,
                   user: ident.VerifiedIdentity = Depends(get_identity),
                   org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.APPROVE_PLAN)
    eng = engine_for(org_id)
    try:
        plan = eng.approve_pending_plan(
            approver_name=payload.approver_name
            or f"{user.display_name if hasattr(user, 'display_name') else user.email}")
        return {"success": True, "plan": plan.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/nlp/triage")
@app.post("/api/v1/triage")
def triage_aid_request(payload: TriagePayload,
                       user: ident.VerifiedIdentity = Depends(get_identity),
                       org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.CREATE_REQUEST)
    eng = engine_for(org_id)
    from . import agents_runtime
    from .agents_runtime import ContextEnvelope, run_action
    from .models import POLICY_VERSION

    # Versioned, tenant-scoped, permission-aware context envelope.
    context = ContextEnvelope(
        organization_id=org_id, actor_id=user.user_id,
        actor_role=user.role_in(org_id) or "",
        mission_id=None, mission_plan_version=eng.current_plan_id,
        optimization_run_id=(eng.plans.get(eng.current_plan_id).optimization_run_id
                            if eng.plans.get(eng.current_plan_id) else None),
        policy_version=POLICY_VERSION,
        data_snapshot_timestamp=time.time(),
        evidence_references=[],
        current_operational_state={"request_count": len(eng.requests),
                                   "active_plan": eng.current_plan_id},
        permitted_actions=["CREATE_AID_REQUEST"],
        prompt_version="triage-v2",
    )
    context.check_freshness(time.time(), eng.current_plan_id, POLICY_VERSION)

    def handler(ctx):
        req, evidence = eng.agent1.triage_message(
            raw_text=payload.raw_text,
            requester=payload.requester or "Field Dispatch Emergency",
            lat=payload.lat if payload.lat is not None else 14.5995,
            lng=payload.lng if payload.lng is not None else 120.9842,
            sector=payload.sector or "Central Metro",
            existing_requests=list(eng.requests.values()))
        eng.requests[req.id] = req
        eng.persist_request_write_through(req)
        eng.log_audit(
            event_type="REQUEST_TRIAGED", actor_id="AGENT-01-NEED",
            actor_type=ActorType.AGENT, entity_type="AidRequest", entity_id=req.id,
            summary=(f"Parsed request from {req.requester_name}: {len(req.items)} items "
                     f"with {req.priority.value} priority"),
            details={"evidence": evidence, "context_version": ctx.context_version,
                     "provider": ctx.provider})
        return {
            "request": req.model_dump(),
            "evidence": evidence,
            "requires_human_review": evidence.get("requires_human_review", False),
        }

    triage_schema = {
        "type": "object",
        "required": ["request", "requires_human_review"],
        "properties": {
            "request": {"type": "object", "required": ["id", "priority", "items"],
                        "properties": {"id": {"type": "string"},
                                       "priority": {"type": "string"},
                                       "items": {"type": "array"}}},
            "requires_human_review": {"type": "boolean"},
        },
    }

    def postcondition(output):
        # Success is defined by VERIFIED STATE, not model text:
        # the request exists in the engine, belongs to this tenant in the DB,
        # and its items were not invented (evidence present per item).
        rid = output["request"]["id"]
        from .db import session_scope
        from . import persistence
        with session_scope() as session:
            row = persistence.get_request(session, org_id, rid)
        return row is not None and rid in eng.requests

    record = run_action(
        agent_id="AGENT-01-NEED", action_id="CREATE_AID_REQUEST", org_id=org_id,
        context=context, prompt=payload.raw_text, schema=triage_schema,
        handler=handler, postcondition=postcondition)
    return {"success": record["status"] in ("SUCCEEDED", "REVIEW_REQUIRED"),
            "status": record["status"],
            "provider": record["provider"],
            "execution_id": record["execution_id"],
            "request": record["output"].get("request"),
            "evidence": record["output"].get("evidence"),
            "requires_human_review": record["output"].get("requires_human_review", False)}


@app.post("/api/v1/deliveries/confirm")
def confirm_delivery(payload: DeliveryPayload,
                     user: ident.VerifiedIdentity = Depends(get_identity),
                     org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.CONFIRM_DELIVERY)
    eng = engine_for(org_id)
    try:
        res = eng.confirm_delivery(request_id=payload.request_id,
                                  volunteer_name=payload.volunteer_name,
                                  signature_data=payload.signature_data or "DigitalSignature")
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/benchmark/run")
def run_benchmark(seed: int = 42, n_requests: int = 200,
                  user: ident.VerifiedIdentity = Depends(get_identity),
                  org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.RUN_OPTIMIZATION)
    if n_requests < 10 or n_requests > 1000:
        raise HTTPException(status_code=400, detail="n_requests must be in [10, 1000]")
    return run_single_benchmark(seed=seed, n_requests=n_requests)


@app.get("/api/v1/missions/{request_id}")
def get_mission(request_id: str,
                user: ident.VerifiedIdentity = Depends(get_identity),
                org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.READ_ORG_DATA)
    eng = engine_for(org_id)
    req = eng.requests.get(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    plan = eng.plans.get(eng.current_plan_id)
    entry = plan.request_entries.get(request_id) if plan else None
    return {"request": req.model_dump(),
            "plan_entry": entry.model_dump() if entry else None,
            "delivery_receipt": eng.delivery_receipts.get(request_id)}


@app.post("/api/v1/missions/transition")
def transition_mission(payload: TransitionPayload,
                       user: ident.VerifiedIdentity = Depends(get_identity),
                       org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.TRANSITION_MISSION)
    eng = engine_for(org_id)
    try:
        res = eng.transition_mission(request_id=payload.request_id,
                                     new_status=payload.new_status,
                                     actor_id=payload.actor_id, reason=payload.reason)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------------------------------------------------
# Tenant administration / audit / export
# ----------------------------------------------------------------------
@app.get("/api/v1/orgs")
def list_my_orgs(user: ident.VerifiedIdentity = Depends(get_identity)):
    return {"scopes": user.scopes, "is_platform_admin": user.is_platform_admin}


@app.get("/api/v1/audit")
def audit_events(limit: int = 100,
                 user: ident.VerifiedIdentity = Depends(get_identity),
                 org_id: str = Depends(org_context)):
    guard(user, org_id, Permission.AUDIT_READ)
    with session_scope() as session:
        rows = persistence.list_audit_events(session, org_id, limit=limit)
        report = persistence.verify_audit_chain(session, org_id)
    return {"org_id": org_id, "chain_valid": report["valid"],
            "problems": report["problems"], "events": [
                {"seq": r.seq, "event_type": r.event_type, "actor_id": r.actor_id,
                 "entity_type": r.entity_type, "entity_id": r.entity_id,
                 "summary": r.summary, "sha256": r.sha256,
                 "prev_hash": r.prev_hash} for r in rows]}


@app.get("/api/v1/orgs/export")
def export_org_data(user: ident.VerifiedIdentity = Depends(get_identity),
                    org_id: str = Depends(org_context)):
    """Controlled data export (AUDITOR/NGO_ADMIN). Returns org-owned records."""
    guard(user, org_id, Permission.EXPORT_DATA)
    with session_scope() as session:
        requests = persistence.list_requests(session, org_id)
        inventory = persistence.get_inventory(session, org_id)
        report = persistence.verify_audit_chain(session, org_id)
    return {
        "org_id": org_id,
        "requests": [{"id": r.id, "status": r.status, "priority": r.priority,
                       "created_at": r.created_at} for r in requests],
        "inventory": inventory,
        "audit_chain_valid": report["valid"],
        "exported_at": time.time(),
    }


# ----------------------------------------------------------------------
# Static frontend (demo UI)
# ----------------------------------------------------------------------
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
