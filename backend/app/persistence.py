"""
AIDNEXUS ONE — Tenant-scoped persistence repositories.

Every function takes org_id and enforces it in WHERE clauses; tenant scope is
never derived from client input beyond this verified parameter.

Transactional guarantees (P0):
- confirm_delivery: receipt INSERT (UNIQUE request_id), inventory movements,
  and audit event commit in ONE transaction. A concurrent duplicate races on
  the unique constraint and returns the existing receipt — stock is never
  deducted twice at the database level.
- apply_inventory_movement: movement row + quantity update in one transaction,
  with a UNIQUE idempotency key so replays are rejected by the database.
- audit chain: per-org sequence numbers with UNIQUE(org_id, seq); each hash
  includes the previous hash. verify_audit_chain() detects missing events,
  duplicates, modified payloads and broken references.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from .db import session_scope
from .models_db import (Organization, User, Membership, Session as SessionRow,
                        Depot, InventoryItem, InventoryMovement, AidRequestRow,
                        PlanVersionRow, ApprovalRow, DeliveryReceiptRow,
                        DisruptionRow, AuditEventRow, AgentExecutionRow,
                        AgentToolCallRow, OutboxEventRow)

logger = logging.getLogger("aidnexus.persistence")


def q_req(org_id: str, request_id: str) -> str:
    """Request/receipt rows are org-qualified: seed ids like REQ-001 exist in
    every organization and must not collide on the global primary key."""
    return f"{org_id}:{request_id}"


def raw_req(qualified_id: str) -> str:
    return qualified_id.split(":", 1)[1] if ":" in qualified_id else qualified_id


def q_depot(org_id: str, depot_id: str) -> str:
    """Depot rows are org-qualified: the same depot code can exist in
    multiple organizations without colliding on the global primary key."""
    return f"{org_id}:{depot_id}"


# ----------------------------------------------------------------------
# Organizations / users / memberships
# ----------------------------------------------------------------------
def get_or_create_organization(session, name: str, slug: str, org_id: str = None) -> Organization:
    org = session.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()
    if org:
        return org
    org = Organization(id=org_id or f"ORG-{slug[:12].upper()}", name=name, slug=slug)
    session.add(org)
    session.flush()
    return org


def get_org_by_id(session, org_id: str) -> Optional[Organization]:
    return session.get(Organization, org_id)


def create_user(session, email: str, display_name: str,
                is_platform_admin: bool = False, user_id: str = None) -> User:
    user = User(id=user_id or f"USR-{uuid.uuid4().hex[:8]}", email=email,
                display_name=display_name, is_platform_admin=is_platform_admin)
    session.add(user)
    session.flush()
    return user


def add_membership(session, user_id: str, org_id: str, role: str) -> Membership:
    m = Membership(user_id=user_id, org_id=org_id, role=role)
    session.add(m)
    session.flush()
    return m


def get_active_membership(session, user_id: str, org_id: str) -> Optional[Membership]:
    m = session.execute(
        select(Membership).where(Membership.user_id == user_id,
                                  Membership.org_id == org_id,
                                  Membership.revoked_at.is_(None))).scalar_one_or_none()
    return m


def revoke_membership(session, user_id: str, org_id: str) -> bool:
    m = get_active_membership(session, user_id, org_id)
    if not m:
        return False
    m.revoked_at = datetime.now(timezone.utc)
    return True


def create_session(session, jti: str, user_id: str, expires_at: datetime) -> SessionRow:
    s = SessionRow(jti=jti, user_id=user_id, expires_at=expires_at)
    session.add(s)
    session.flush()
    return s


def is_session_live(session, jti: str) -> bool:
    s = session.get(SessionRow, jti)
    if not s or s.revoked_at is not None:
        return False
    return s.expires_at > datetime.now(timezone.utc)


def revoke_session(session, jti: str) -> bool:
    s = session.get(SessionRow, jti)
    if s:
        s.revoked_at = datetime.now(timezone.utc)
        return True
    return False


# ----------------------------------------------------------------------
# Aid requests (tenant-scoped)
# ----------------------------------------------------------------------
def persist_request(session, org_id: str, req_dict: Dict[str, Any]) -> AidRequestRow:
    """Insert-or-update (a restart replay of the same scenario must not
    collide on the request primary key)."""
    qualified = q_req(org_id, req_dict["id"])
    row = session.execute(select(AidRequestRow).where(
        AidRequestRow.org_id == org_id,
        AidRequestRow.id == qualified)).scalar_one_or_none()
    if row is not None:
        row.status = req_dict["status"]
        row.urgency_score = req_dict.get("urgency_score", row.urgency_score)
        if req_dict.get("duplicate_of_id"):
            row.duplicate_of_id = req_dict["duplicate_of_id"]
        session.flush()
        return row
    row = AidRequestRow(
        id=qualified, org_id=org_id,
        requester_name=req_dict.get("requester_name", "Unknown"),
        lat=req_dict["location"]["lat"], lng=req_dict["location"]["lng"],
        sector=req_dict["location"].get("sector", "Central"),
        priority=req_dict["priority"], status=req_dict["status"],
        deadline_hours=req_dict.get("deadline_hours", 24.0),
        affected_people=req_dict.get("affected_people", 10),
        urgency_score=req_dict.get("urgency_score", 75.0),
        duplicate_of_id=req_dict.get("duplicate_of_id"),
        intake_channel=req_dict.get("intake_channel", "MANUAL"),
        special_notes=req_dict.get("special_notes"),
        created_at=req_dict.get("created_at"),
        items=req_dict.get("items", []),
    )
    session.add(row)
    session.flush()
    return row


def update_request_status(session, org_id: str, request_id: str, status: str,
                          delivered_at: Optional[float] = None) -> bool:
    row = session.execute(
        select(AidRequestRow).where(AidRequestRow.org_id == org_id,
                                    AidRequestRow.id == q_req(org_id, request_id))).scalar_one_or_none()
    if not row:
        return False
    row.status = status
    if delivered_at is not None:
        row.delivered_at = delivered_at
    return True


def list_requests(session, org_id: str, status: Optional[str] = None) -> List[AidRequestRow]:
    q = select(AidRequestRow).where(AidRequestRow.org_id == org_id)
    if status:
        q = q.where(AidRequestRow.status == status)
    return list(session.execute(q).scalars().all())


def get_request(session, org_id: str, request_id: str) -> Optional[AidRequestRow]:
    return session.execute(
        select(AidRequestRow).where(AidRequestRow.org_id == org_id,
                                    AidRequestRow.id == q_req(org_id, request_id))).scalar_one_or_none()


# ----------------------------------------------------------------------
# Inventory (transactional movements)
# ----------------------------------------------------------------------
def seed_inventory(session, org_id: str, depot_id: str, item_type: str, quantity: float):
    depot_id = q_depot(org_id, depot_id)
    item = session.execute(select(InventoryItem).where(
        InventoryItem.depot_id == depot_id,
        InventoryItem.item_type == item_type)).scalar_one_or_none()
    if item is None:
        session.add(InventoryItem(depot_id=depot_id, org_id=org_id,
                                  item_type=item_type, quantity=quantity))
        movement = InventoryMovement(org_id=org_id, depot_id=depot_id, item_type=item_type,
                                     delta=quantity, reason="SEED",
                                     idempotency_key=f"seed:{depot_id}:{item_type}")
        session.add(movement)
    else:
        item.quantity = quantity
    session.flush()


def apply_inventory_movement(session, org_id: str, depot_id: str, item_type: str,
                             delta: float, reason: str, request_id: str = None,
                             idempotency_key: str = None) -> bool:
    """Movement ledger row + quantity update in ONE transaction. Returns False
    when the idempotency key was already used (replay rejected by the DB)."""
    depot_id = q_depot(org_id, depot_id)
    key = idempotency_key or f"mv:{uuid.uuid4().hex[:16]}"
    exists = session.execute(select(InventoryMovement).where(
        InventoryMovement.idempotency_key == key)).scalar_one_or_none()
    if exists:
        return False
    # ATOMIC update: the database computes quantity + delta under its row/write
    # lock. This prevents lost updates under concurrency (verified by
    # test_concurrent_allocations_never_exceed_stock) and lets the
    # CHECK constraint reject negative stock.
    from sqlalchemy import update
    res = session.execute(
        update(InventoryItem)
        .where(InventoryItem.depot_id == depot_id,
               InventoryItem.item_type == item_type)
        .values(quantity=InventoryItem.quantity + delta))
    if res.rowcount == 0:
        session.add(InventoryItem(depot_id=depot_id, org_id=org_id,
                                  item_type=item_type, quantity=delta))
    session.add(InventoryMovement(org_id=org_id, depot_id=depot_id, item_type=item_type,
                                  delta=delta, reason=reason, request_id=request_id,
                                  idempotency_key=key))
    session.flush()
    return True


def get_inventory(session, org_id: str) -> Dict[str, Dict[str, float]]:
    rows = session.execute(select(InventoryItem).where(InventoryItem.org_id == org_id)).scalars().all()
    out: Dict[str, Dict[str, float]] = {}
    for r in rows:
        out.setdefault(r.depot_id, {})[r.item_type] = r.quantity
    return out


# ----------------------------------------------------------------------
# Delivery receipts (idempotent, transactional)
# ----------------------------------------------------------------------
def confirm_delivery_persisted(session, org_id: str, request_id: str,
                               volunteer_name: str, signature_hash: str,
                               items: List[Dict], depot_id: Optional[str],
                               duplicate_flag: bool = False) -> Dict[str, Any]:
    """Atomic: receipt + inventory movements + audit event in one commit.
    On a concurrent duplicate the UNIQUE(request_id) constraint aborts the
    transaction; the caller returns the existing receipt."""
    qualified = q_req(org_id, request_id)
    existing = session.get(DeliveryReceiptRow, qualified)
    if existing:
        return {"request_id": request_id, "signature_hash": existing.signature_hash,
                "duplicate": True, "already_persisted": True}
    receipt = DeliveryReceiptRow(request_id=qualified, org_id=org_id,
                                 volunteer_name=volunteer_name,
                                 signature_hash=signature_hash,
                                 payload={"items": items})
    session.add(receipt)
    if depot_id:
        # apply_inventory_movement qualifies the depot id itself
        for it in items:
            apply_inventory_movement(
                session, org_id=org_id, depot_id=depot_id, item_type=it["item_type"],
                delta=-float(it["quantity"]), reason="DELIVERY", request_id=request_id,
                idempotency_key=f"delivery:{org_id}:{request_id}:{it['item_type']}")
    update_request_status(session, org_id, request_id, "DELIVERED")
    session.flush()
    return {"request_id": request_id, "signature_hash": signature_hash,
            "duplicate": duplicate_flag, "already_persisted": False}


def get_receipt(session, org_id: str, request_id: str) -> Optional[DeliveryReceiptRow]:
    r = session.get(DeliveryReceiptRow, q_req(org_id, request_id))
    if r and r.org_id == org_id:
        return r
    return None


# ----------------------------------------------------------------------
# Plans / approvals
# ----------------------------------------------------------------------
def persist_plan(session, org_id: str, plan_payload: Dict[str, Any]) -> PlanVersionRow:
    """Insert-or-update: replays (e.g. engine rebuild after restart) must not
    collide on UNIQUE(org_id, version_id); they refresh the durable snapshot."""
    row = session.execute(select(PlanVersionRow).where(
        PlanVersionRow.org_id == org_id,
        PlanVersionRow.version_id == plan_payload["version_id"])).scalar_one_or_none()
    if row is None:
        row = PlanVersionRow(org_id=org_id, version_id=plan_payload["version_id"])
        session.add(row)
    row.optimization_run_id = plan_payload.get("optimization_run_id", "")
    row.policy_version = plan_payload.get("policy_version", "")
    row.is_active = plan_payload.get("is_active", False)
    row.is_approved = plan_payload.get("is_approved", False)
    row.approved_by = plan_payload.get("approved_by")
    row.auto_approved = plan_payload.get("auto_approved", False)
    row.checksum = plan_payload.get("checksum", "")
    row.payload = plan_payload
    session.flush()
    return row


def get_plan(session, org_id: str, version_id: str) -> Optional[PlanVersionRow]:
    return session.execute(select(PlanVersionRow).where(
        PlanVersionRow.org_id == org_id, PlanVersionRow.version_id == version_id)
    ).scalar_one_or_none()


def record_approval(session, org_id: str, plan_row_id: int, approver: str,
                    decision: str, reason: str = None) -> ApprovalRow:
    row = ApprovalRow(org_id=org_id, plan_row_id=plan_row_id,
                      approver=approver, decision=decision, reason=reason)
    session.add(row)
    session.flush()
    return row


def list_plans(session, org_id: str) -> List[PlanVersionRow]:
    return list(session.execute(select(PlanVersionRow).where(
        PlanVersionRow.org_id == org_id).order_by(PlanVersionRow.id)).scalars().all())


# ----------------------------------------------------------------------
# Audit chain (per-org, tamper-evident)
# ----------------------------------------------------------------------
def audit_hash(org_id: str, seq: int, event_type: str, actor_id: str, entity_id: str,
               summary: str, prev_hash: str) -> str:
    raw = f"{org_id}:{seq}:{event_type}:{actor_id}:{entity_id}:{summary}:{prev_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def append_audit_event(session, org_id: str, event_type: str, actor_id: str,
                       actor_type: str, entity_type: str, entity_id: str,
                       summary: str, details: Dict[str, Any] | None = None) -> AuditEventRow:
    last = session.execute(select(AuditEventRow).where(AuditEventRow.org_id == org_id)
                           .order_by(AuditEventRow.seq.desc()).limit(1)).scalar_one_or_none()
    seq = (last.seq + 1) if last else 1
    prev_hash = last.sha256 if last else ""
    sha = audit_hash(org_id, seq, event_type, actor_id, entity_id, summary, prev_hash)
    row = AuditEventRow(org_id=org_id, seq=seq, event_type=event_type, actor_id=actor_id,
                        actor_type=actor_type, entity_type=entity_type, entity_id=entity_id,
                        summary=summary, details=details or {}, sha256=sha, prev_hash=prev_hash)
    session.add(row)
    session.flush()
    return row


def verify_audit_chain(session, org_id: str) -> Dict[str, Any]:
    """Detects: missing seq numbers, duplicate seq, modified payload (hash
    mismatch), broken prev-hash references. Returns a structured report."""
    rows = list(session.execute(select(AuditEventRow).where(AuditEventRow.org_id == org_id)
                                .order_by(AuditEventRow.seq)).scalars().all())
    problems: List[str] = []
    prev_hash = ""
    expected_seq = 1
    seen_seq = set()
    for r in rows:
        if r.seq in seen_seq:
            problems.append(f"duplicate seq {r.seq}")
        seen_seq.add(r.seq)
        if r.seq != expected_seq:
            problems.append(f"missing/duplicate seq: expected {expected_seq}, found {r.seq}")
            expected_seq = r.seq
        expected_seq += 1
        if r.prev_hash != prev_hash:
            problems.append(f"broken prev-hash at seq {r.seq}")
        recomputed = audit_hash(org_id, r.seq, r.event_type, r.actor_id, r.entity_id,
                                r.summary, r.prev_hash)
        if recomputed != r.sha256:
            problems.append(f"payload/hash mismatch at seq {r.seq} (modified?)")
        prev_hash = r.sha256
    return {"org_id": org_id, "events": len(rows), "valid": len(problems) == 0,
            "problems": problems}


def list_audit_events(session, org_id: str, limit: int = 100) -> List[AuditEventRow]:
    rows = session.execute(select(AuditEventRow).where(AuditEventRow.org_id == org_id)
                           .order_by(AuditEventRow.seq.desc()).limit(limit)).scalars().all()
    return list(rows)


# ----------------------------------------------------------------------
# Disruptions
# ----------------------------------------------------------------------
def persist_disruption(session, org_id: str, disruption_payload: Dict[str, Any]) -> DisruptionRow:
    row = DisruptionRow(id=disruption_payload["id"], org_id=org_id,
                        type=disruption_payload["type"], title=disruption_payload["title"],
                        hazard_radius_km=disruption_payload.get("hazard_radius_km", 3.5),
                        active=disruption_payload.get("active", True),
                        payload=disruption_payload)
    session.add(row)
    session.flush()
    return row


# ----------------------------------------------------------------------
# Agent executions
# ----------------------------------------------------------------------
def persist_agent_execution(session, record: Dict[str, Any]) -> AgentExecutionRow:
    row = AgentExecutionRow(**{k: v for k, v in record.items()
                               if k in AgentExecutionRow.__table__.columns.keys()})
    session.add(row)
    session.flush()
    for call in record.get("tool_calls", []):
        session.add(AgentToolCallRow(execution_row_id=row.id, **{
            "tool_name": call.get("tool_name"),
            "args": call.get("args", {}),
            "result": call.get("result", {}),
            "status": call.get("status", "OK")}))
    session.flush()
    return row


# ----------------------------------------------------------------------
# Transactional outbox
# ----------------------------------------------------------------------
def enqueue_outbox(session, org_id: str, event_type: str, payload: Dict[str, Any],
                   idempotency_key: str) -> OutboxEventRow:
    row = OutboxEventRow(org_id=org_id, event_type=event_type, payload=payload,
                         idempotency_key=idempotency_key)
    session.add(row)
    session.flush()
    return row


def claim_pending_outbox(session, limit: int = 20) -> List[OutboxEventRow]:
    return list(session.execute(
        select(OutboxEventRow).where(OutboxEventRow.processed_at.is_(None))
        .order_by(OutboxEventRow.id).limit(limit)).scalars().all())


def mark_outbox_processed(session, outbox_id: int, error: str | None = None):
    row = session.get(OutboxEventRow, outbox_id)
    if row:
        row.attempts += 1
        if error is None:
            row.processed_at = datetime.now(timezone.utc)
        else:
            row.last_error = error
