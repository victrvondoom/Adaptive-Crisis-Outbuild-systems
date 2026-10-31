"""Phase IV domain logic: beneficiary consent, cross-NGO resource transfers,
procurement-to-inventory, evidence-linked impact reports, outbox dispatch.

All functions open their own DB session (same pattern as persistence_phase3)
and are strictly tenant-scoped. Every consequential mutation appends an audit
event in the same transaction. Inventory changes go ONLY through
persistence.apply_inventory_movement — no duplicate ledger logic.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select

from .db import session_scope
from . import persistence
from .models_db import (BeneficiaryConsentRow, ProcurementRow, ResourceTransferRow,
                        SupplierRow, Organization, DeliveryReceiptRow,
                        InventoryMovement, AuditEventRow)


def _now():
    return datetime.now(timezone.utc)


def _uid(prefix: str, n: int = 10) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:n]}"


# ======================================================================
# Beneficiary consent (Mission A)
# ======================================================================

def record_consent(org_id: str, request_id: str, granted_by: str,
                   consent_scope: str = "ASSISTANCE",
                   evidence: Optional[str] = None) -> Dict[str, Any]:
    with session_scope() as session:
        existing = session.execute(select(BeneficiaryConsentRow).where(
            BeneficiaryConsentRow.org_id == org_id,
            BeneficiaryConsentRow.request_id == request_id)
        ).scalar_one_or_none()
        if existing and not existing.revoked_at:
            return {"consent_id": existing.id, "status": "GRANTED",
                    "already_recorded": True}
        row = BeneficiaryConsentRow(id=_uid("CON"), org_id=org_id,
                                    request_id=request_id,
                                    consent_scope=consent_scope,
                                    granted_by=granted_by, evidence=evidence)
        session.add(row)
        persistence.append_audit_event(
            session, org_id, event_type="CONSENT_GRANTED", actor_id=granted_by,
            actor_type="HUMAN", entity_type="AidRequest", entity_id=request_id,
            summary=f"Beneficiary consent recorded for request {request_id} "
                    f"(scope={consent_scope})",
            details={"consent_id": row.id, "scope": consent_scope})
        session.flush()
        return {"consent_id": row.id, "status": "GRANTED",
                "already_recorded": False}


def revoke_consent(org_id: str, request_id: str, actor: str) -> bool:
    with session_scope() as session:
        row = session.execute(select(BeneficiaryConsentRow).where(
            BeneficiaryConsentRow.org_id == org_id,
            BeneficiaryConsentRow.request_id == request_id)
        ).scalar_one_or_none()
        if not row or row.revoked_at:
            return False
        row.revoked_at = _now()
        persistence.append_audit_event(
            session, org_id, event_type="CONSENT_REVOKED", actor_id=actor,
            actor_type="HUMAN", entity_type="AidRequest", entity_id=request_id,
            summary=f"Beneficiary withdrew consent for request {request_id}")
        session.flush()
        return True


def get_consent(org_id: str, request_id: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        row = session.execute(select(BeneficiaryConsentRow).where(
            BeneficiaryConsentRow.org_id == org_id,
            BeneficiaryConsentRow.request_id == request_id)
        ).scalar_one_or_none()
        if not row:
            return None
        return {"consent_id": row.id, "status": "REVOKED" if row.revoked_at else "GRANTED",
                "scope": row.consent_scope,
                "granted_by": row.granted_by,
                "granted_at": row.granted_at.isoformat() if row.granted_at else None,
                "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None}


def consent_revoked(org_id: str, request_id: str) -> bool:
    c = get_consent(org_id, request_id)
    return bool(c and c["status"] == "REVOKED")


# ======================================================================
# Cross-NGO resource transfers (Mission C)
# ======================================================================
# Transitions are enforced inline in the functions below:
# PROPOSED -> SOURCE_APPROVED -> DEST_APPROVED -> DISPATCHED -> RECEIVED,
# with CANCELLED from any pre-dispatch state and FAILED at dispatch.


def _transfer_row(session, transfer_id: str) -> Optional[ResourceTransferRow]:
    return session.get(ResourceTransferRow, transfer_id)


def create_transfer(source_org_id: str, dest_org_id: str, source_depot_id: str,
                    dest_depot_id: str, item_type: str, quantity: float,
                    proposed_by: str, reason: Optional[str] = None) -> Dict[str, Any]:
    if source_org_id == dest_org_id:
        raise ValueError("Source and destination organizations must differ")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    with session_scope() as session:
        dest_org = persistence.get_org_by_id(session, dest_org_id)
        if not dest_org or not dest_org.is_active:
            raise ValueError("Destination organization not found or inactive")
        # source depot must belong to the source org; stock must cover the offer
        qualified_source = persistence.ensure_depot(session, source_org_id,
                                                    source_depot_id)
        inv = session.execute(select(persistence.InventoryItem).where(
            persistence.InventoryItem.org_id == source_org_id,
            persistence.InventoryItem.item_type == item_type)).scalars().all()
        available = sum(i.quantity for i in inv
                        if i.depot_id == qualified_source)
        if available < quantity:
            raise ValueError(
                f"Insufficient stock: {available} < {quantity} of {item_type}")
        # destination depot must exist in the destination org
        persistence.ensure_depot(session, dest_org_id, dest_depot_id)
        row = ResourceTransferRow(
            id=_uid("XFR", 12), source_org_id=source_org_id, dest_org_id=dest_org_id,
            source_depot_id=source_depot_id, dest_depot_id=dest_depot_id,
            item_type=item_type, quantity=quantity, reason=reason,
            proposed_by=proposed_by)
        session.add(row)
        persistence.append_audit_event(
            session, source_org_id, event_type="TRANSFER_PROPOSED",
            actor_id=proposed_by, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id,
            summary=(f"Proposed transfer of {quantity} {item_type} to "
                     f"{dest_org_id} (needs source + destination approval)"),
            details={"dest_org_id": dest_org_id, "item_type": item_type,
                     "quantity": quantity})
        session.flush()
        return _transfer_dict(row)


def _transfer_dict(row: ResourceTransferRow) -> Dict[str, Any]:
    return {"transfer_id": row.id, "source_org_id": row.source_org_id,
            "dest_org_id": row.dest_org_id,
            "source_depot_id": row.source_depot_id,
            "dest_depot_id": row.dest_depot_id, "item_type": row.item_type,
            "quantity": row.quantity, "status": row.status, "reason": row.reason,
            "proposed_by": row.proposed_by,
            "source_approved_by": row.source_approved_by,
            "dest_approved_by": row.dest_approved_by,
            "failed_reason": row.failed_reason,
            "created_at": row.created_at.isoformat() if row.created_at else None}


def approve_transfer(transfer_id: str, acting_org_id: str, actor: str,
                     which: str) -> Dict[str, Any]:
    """which='source' or 'dest'. Approvals are sequential: source first, then
    destination — an explicit dual-approval contract."""
    with session_scope() as session:
        row = _transfer_row(session, transfer_id)
        if not row or acting_org_id not in (row.source_org_id, row.dest_org_id):
            raise LookupError("Transfer not found for this organization")
        if which == "source":
            if acting_org_id != row.source_org_id:
                raise PermissionError("Only the source organization can approve this step")
            if row.status != "PROPOSED":
                raise ValueError(f"Transfer is {row.status}, expected PROPOSED")
            row.status = "SOURCE_APPROVED"
            row.source_approved_by = actor
            row.source_approved_at = _now()
        else:
            if acting_org_id != row.dest_org_id:
                raise PermissionError("Only the destination organization can approve this step")
            if row.status != "SOURCE_APPROVED":
                raise ValueError(f"Transfer is {row.status}, expected SOURCE_APPROVED")
            row.status = "DEST_APPROVED"
            row.dest_approved_by = actor
            row.dest_approved_at = _now()
        persistence.append_audit_event(
            session, acting_org_id, event_type="TRANSFER_APPROVED",
            actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id,
            summary=f"{which.capitalize()} organization approved transfer {row.id}")
        session.flush()
        return _transfer_dict(row)


def dispatch_transfer(transfer_id: str, acting_org_id: str, actor: str) -> Dict[str, Any]:
    """Moves stock: -qty at source depot, +qty at destination depot. Ledger rows
    are idempotency-keyed off the transfer id, so a replay cannot double-move."""
    with session_scope() as session:
        row = _transfer_row(session, transfer_id)
        if not row or acting_org_id not in (row.source_org_id, row.dest_org_id):
            raise LookupError("Transfer not found for this organization")
        if row.status != "DEST_APPROVED":
            raise ValueError(f"Transfer is {row.status}, expected DEST_APPROVED")
        # Re-check availability at dispatch time (stock may have changed since approval)
        inv = session.execute(select(persistence.InventoryItem).where(
            persistence.InventoryItem.org_id == row.source_org_id,
            persistence.InventoryItem.depot_id == persistence.q_depot(
                row.source_org_id, row.source_depot_id),
            persistence.InventoryItem.item_type == row.item_type)).scalar_one_or_none()
        available = inv.quantity if inv else 0.0
        if available < row.quantity:
            row.status = "FAILED"
            row.failed_reason = (f"Stock shortfall at dispatch: {available} < "
                                 f"{row.quantity} {row.item_type}")
            persistence.append_audit_event(
                session, row.source_org_id, event_type="TRANSFER_FAILED",
                actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
                entity_id=row.id, summary=row.failed_reason)
            session.flush()
            return _transfer_dict(row)
        out_ok = persistence.apply_inventory_movement(
            session, row.source_org_id, row.source_depot_id, row.item_type,
            delta=-row.quantity, reason="TRANSFER_OUT",
            idempotency_key=f"xfr:{row.id}:out")
        in_ok = persistence.apply_inventory_movement(
            session, row.dest_org_id, row.dest_depot_id, row.item_type,
            delta=row.quantity, reason="TRANSFER_IN",
            idempotency_key=f"xfr:{row.id}:in")
        if not out_ok or not in_ok:
            raise RuntimeError("Idempotency key collision on transfer dispatch")
        row.status = "DISPATCHED"
        row.dispatched_at = _now()
        # audit in BOTH orgs (each sees only its own event)
        persistence.append_audit_event(
            session, row.source_org_id, event_type="TRANSFER_DISPATCHED",
            actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id,
            summary=f"Dispatched {row.quantity} {row.item_type} to {row.dest_org_id}")
        persistence.append_audit_event(
            session, row.dest_org_id, event_type="TRANSFER_DISPATCHED",
            actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id,
            summary=f"Received dispatch of {row.quantity} {row.item_type} "
                    f"from {row.source_org_id}")
        session.flush()
        return _transfer_dict(row)


def receive_transfer(transfer_id: str, acting_org_id: str, actor: str) -> Dict[str, Any]:
    with session_scope() as session:
        row = _transfer_row(session, transfer_id)
        if not row or acting_org_id not in (row.source_org_id, row.dest_org_id):
            raise LookupError("Transfer not found for this organization")
        if row.status != "DISPATCHED":
            raise ValueError(f"Transfer is {row.status}, expected DISPATCHED")
        row.status = "RECEIVED"
        row.received_at = _now()
        persistence.append_audit_event(
            session, row.dest_org_id, event_type="TRANSFER_RECEIVED",
            actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id,
            summary=f"Destination confirmed handover of transfer {row.id}")
        session.flush()
        return _transfer_dict(row)


def cancel_transfer(transfer_id: str, acting_org_id: str, actor: str,
                    reason: str) -> Dict[str, Any]:
    with session_scope() as session:
        row = _transfer_row(session, transfer_id)
        if not row or acting_org_id not in (row.source_org_id, row.dest_org_id):
            raise LookupError("Transfer not found for this organization")
        if row.status not in ("PROPOSED", "SOURCE_APPROVED", "DEST_APPROVED"):
            raise ValueError(f"Transfer in state {row.status} cannot be cancelled")
        row.status = "CANCELLED"
        row.failed_reason = reason
        persistence.append_audit_event(
            session, acting_org_id, event_type="TRANSFER_CANCELLED",
            actor_id=actor, actor_type="HUMAN", entity_type="ResourceTransfer",
            entity_id=row.id, summary=f"Transfer cancelled: {reason}")
        session.flush()
        return _transfer_dict(row)


def list_transfers(org_id: str) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(select(ResourceTransferRow).where(
            (ResourceTransferRow.source_org_id == org_id)
            | (ResourceTransferRow.dest_org_id == org_id))
            .order_by(ResourceTransferRow.created_at.desc())).scalars().all()
        return [_transfer_dict(r) for r in rows]


# ======================================================================
# Procurement (Mission D)
# ======================================================================

def register_supplier(org_id: str, name: str, verified: bool = False) -> Dict[str, Any]:
    with session_scope() as session:
        row = SupplierRow(id=_uid("SUP"), org_id=org_id, name=name, verified=verified)
        session.add(row)
        persistence.append_audit_event(
            session, org_id, event_type="SUPPLIER_REGISTERED", actor_id="org",
            actor_type="HUMAN", entity_type="Supplier", entity_id=row.id,
            summary=f"Supplier registered: {name} (verified={verified})")
        session.flush()
        return {"supplier_id": row.id, "name": row.name, "verified": row.verified}


def verify_supplier(org_id: str, supplier_id: str) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(SupplierRow, supplier_id)
        if not row or row.org_id != org_id:
            raise LookupError("Supplier not found for this organization")
        row.verified = True
        persistence.append_audit_event(
            session, org_id, event_type="SUPPLIER_VERIFIED", actor_id="org",
            actor_type="HUMAN", entity_type="Supplier", entity_id=supplier_id,
            summary=f"Supplier {row.name} verified for procurement")
        session.flush()
        return {"supplier_id": row.id, "name": row.name, "verified": True}


def list_suppliers(org_id: str) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(select(SupplierRow).where(
            SupplierRow.org_id == org_id).order_by(SupplierRow.created_at)).scalars().all()
        return [{"supplier_id": r.id, "name": r.name, "verified": r.verified} for r in rows]


def set_org_budget(org_id: str, budget_cents: Optional[int]) -> Dict[str, Any]:
    with session_scope() as session:
        org = persistence.get_org_by_id(session, org_id)
        if not org:
            raise LookupError("Organization not found")
        org.budget_cents = budget_cents
        session.flush()
        return {"org_id": org_id, "budget_cents": budget_cents}


def _proc_dict(row: ProcurementRow) -> Dict[str, Any]:
    return {"procurement_id": row.id, "supplier_id": row.supplier_id,
            "depot_id": row.depot_id, "item_type": row.item_type,
            "quantity": row.quantity, "unit_cost_cents": row.unit_cost_cents,
            "total_cost_cents": row.total_cost_cents, "status": row.status,
            "proposed_by": row.proposed_by, "approved_by": row.approved_by,
            "received_quantity": row.received_quantity,
            "discrepancy_note": row.discrepancy_note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "received_at": row.received_at.isoformat() if row.received_at else None}


def create_procurement(org_id: str, supplier_id: str, depot_id: str,
                       item_type: str, quantity: float, unit_cost_cents: int,
                       proposed_by: str) -> Dict[str, Any]:
    if quantity <= 0 or unit_cost_cents < 0:
        raise ValueError("Quantity must be positive and cost non-negative")
    with session_scope() as session:
        supplier = session.get(SupplierRow, supplier_id)
        if not supplier or supplier.org_id != org_id:
            raise LookupError("Supplier not found for this organization")
        total = int(quantity * unit_cost_cents)
        row = ProcurementRow(
            id=_uid("PRC"), org_id=org_id, supplier_id=supplier_id,
            depot_id=depot_id, item_type=item_type, quantity=quantity,
            unit_cost_cents=unit_cost_cents, total_cost_cents=total,
            proposed_by=proposed_by)
        session.add(row)
        persistence.ensure_depot(session, org_id, depot_id)
        persistence.append_audit_event(
            session, org_id, event_type="PROCUREMENT_PROPOSED",
            actor_id=proposed_by, actor_type="HUMAN", entity_type="Procurement",
            entity_id=row.id,
            summary=(f"Procurement proposal: {quantity} {item_type} at "
                     f"{unit_cost_cents}c/unit from {supplier.name}"),
            details={"total_cost_cents": total, "supplier_verified": supplier.verified})
        session.flush()
        return _proc_dict(row)


def approve_procurement(org_id: str, procurement_id: str, actor: str) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(ProcurementRow, procurement_id)
        if not row or row.org_id != org_id:
            raise LookupError("Procurement not found for this organization")
        if row.status != "PROPOSED":
            raise ValueError(f"Procurement is {row.status}, expected PROPOSED")
        supplier = session.get(SupplierRow, row.supplier_id)
        if not supplier or not supplier.verified:
            raise ValueError("Only verified suppliers may be procured from")
        # Budget check: outstanding (approved, not yet received) + this proposal
        # must fit the org budget when a budget is set.
        org = persistence.get_org_by_id(session, org_id)
        if org.budget_cents is not None:
            outstanding = session.execute(select(ProcurementRow).where(
                ProcurementRow.org_id == org_id,
                ProcurementRow.status.in_(["APPROVED", "ORDERED"]))).scalars().all()
            committed = sum(p.total_cost_cents for p in outstanding)
            if committed + row.total_cost_cents > org.budget_cents:
                raise ValueError(
                    f"Budget exceeded: committed {committed}c + this "
                    f"{row.total_cost_cents}c > budget {org.budget_cents}c")
        row.status = "APPROVED"
        row.approved_by = actor
        row.approved_at = _now()
        persistence.append_audit_event(
            session, org_id, event_type="PROCUREMENT_APPROVED",
            actor_id=actor, actor_type="HUMAN", entity_type="Procurement",
            entity_id=row.id,
            summary=f"Procurement {row.id} approved: {row.quantity} {row.item_type}")
        session.flush()
        return _proc_dict(row)


def receive_procurement(org_id: str, procurement_id: str, received_quantity: float,
                        actor: str, discrepancy_note: Optional[str] = None) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(ProcurementRow, procurement_id)
        if not row or row.org_id != org_id:
            raise LookupError("Procurement not found for this organization")
        if row.status not in ("APPROVED", "ORDERED"):
            raise ValueError(f"Procurement is {row.status}, expected APPROVED/ORDERED")
        if received_quantity < 0 or received_quantity > row.quantity:
            raise ValueError("Received quantity out of range [0, ordered]")
        ok = persistence.apply_inventory_movement(
            session, org_id, row.depot_id, row.item_type,
            delta=received_quantity, reason="PROCUREMENT_RECEIPT",
            idempotency_key=f"proc:{row.id}:receipt")
        if not ok:
            raise RuntimeError("Duplicate receipt rejected (idempotency)")
        row.received_quantity = received_quantity
        row.received_at = _now()
        if received_quantity != row.quantity:
            row.status = "DISCREPANCY"
            row.discrepancy_note = (discrepancy_note or
                                    f"Ordered {row.quantity}, received {received_quantity}")
        else:
            row.status = "RECEIVED"
        persistence.append_audit_event(
            session, org_id, event_type="PROCUREMENT_RECEIVED",
            actor_id=actor, actor_type="HUMAN", entity_type="Procurement",
            entity_id=row.id,
            summary=(f"Goods received for {row.id}: {received_quantity} of "
                     f"{row.quantity} {row.item_type} into {row.depot_id}"),
            details={"discrepancy": received_quantity != row.quantity})
        session.flush()
        return _proc_dict(row)


def list_procurements(org_id: str) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(select(ProcurementRow).where(
            ProcurementRow.org_id == org_id)
            .order_by(ProcurementRow.created_at.desc())).scalars().all()
        return [_proc_dict(r) for r in rows]


# ======================================================================
# Impact report (Mission E)
# ======================================================================

def impact_report(org_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Evidence-linked impact report recomputed from authoritative rows.
    Provenance: sha256 over the canonical JSON of the computed content —
    consumers can verify the report has not been altered since generation."""
    if request_id:
        return _request_impact_report(org_id, request_id)
    with session_scope() as session:
        reqs = persistence.list_requests(session, org_id)
        total = len(reqs)
        by_status: Dict[str, int] = {}
        for r in reqs:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        receipts = session.execute(select(DeliveryReceiptRow).where(
            DeliveryReceiptRow.org_id == org_id)).scalars().all()
        delivered = by_status.get("DELIVERED", 0)
        critical_total = sum(1 for r in reqs if r.priority == "CRITICAL")
        critical_delivered = sum(
            1 for r in reqs if r.priority == "CRITICAL" and r.status == "DELIVERED")
        movements = session.execute(select(InventoryMovement).where(
            InventoryMovement.org_id == org_id)).scalars().all()
        consumed_by_delivery = -sum(m.delta for m in movements
                                    if m.reason == "DELIVERY" and m.delta < 0)
        gained_by_receipts = sum(m.delta for m in movements
                                if m.reason in ("PROCUREMENT_RECEIPT", "TRANSFER_IN"))
        chain = persistence.verify_audit_chain(session, org_id)
        report = {
            "org_id": org_id,
            "generated_at": _now().isoformat(),
            "level": "ORGANIZATION",
            "requests_total": total,
            "requests_by_status": by_status,
            "delivery_receipts": len(receipts),
            # Formula (metric registry): delivered requests / total requests.
            "fulfillment_rate": round(delivered / total, 4) if total else None,
            "fulfillment_formula": "delivered_requests / total_requests",
            # Critical coverage: delivered CRITICAL / total CRITICAL.
            "critical_coverage": (round(critical_delivered / critical_total, 4)
                                  if critical_total else None),
            "critical_total": critical_total,
            "critical_delivered": critical_delivered,
            "inventory_consumed_by_deliveries": consumed_by_delivery,
            "inventory_gained_by_replenishment": gained_by_receipts,
            "movement_count": len(movements),
            "audit_chain_valid": bool(chain.get("valid", False)),
            "audit_chain_report": chain,
            "actual_vs_estimated": (
                "Delivered counts are ACTUAL (persisted receipts). Pending and "
                "in-flight counts are operational states, not outcomes."),
            "missing_evidence": [
                f"request {persistence.raw_req(r.id)} without receipt" for r in reqs
                if r.status == "DELIVERED"
                and not session.get(DeliveryReceiptRow, r.id)
            ][:20],
        }
        report["provenance_sha256"] = hashlib.sha256(
            json.dumps(report, sort_keys=True, default=str).encode()).hexdigest()
        return report


def _request_impact_report(org_id: str, request_id: str) -> Dict[str, Any]:
    with session_scope() as session:
        req = persistence.get_request(session, org_id, request_id)
        if not req:
            raise LookupError("Request not found")
        receipt = persistence.get_receipt(session, org_id, request_id)
        movements = session.execute(select(InventoryMovement).where(
            InventoryMovement.org_id == org_id,
            InventoryMovement.request_id == request_id)).scalars().all()
        events = session.execute(select(AuditEventRow).where(
            AuditEventRow.org_id == org_id,
            AuditEventRow.entity_id == request_id)
            .order_by(AuditEventRow.seq)).scalars().all()
        consent = get_consent(org_id, request_id)
        report = {
            "org_id": org_id,
            "request_id": request_id,
            "generated_at": _now().isoformat(),
            "level": "REQUEST",
            "request": {"requester": req.requester_name,
                        "priority": req.priority, "status": req.status,
                        "delivered_at": req.delivered_at,
                        "items": req.items},
            "delivery_receipt": ({"volunteer": receipt.volunteer_name,
                                  "signature_hash": receipt.signature_hash,
                                  "delivered_at": receipt.delivered_at.isoformat(),
                                  "items": receipt.payload.get("items", [])}
                                 if receipt else None),
            "outcome": ("DELIVERED_ACTUAL" if receipt else
                        {"status": req.status,
                         "note": "No persisted receipt: not yet an outcome"}),
            "inventory_movements": [
                {"depot_id": m.depot_id, "item_type": m.item_type,
                 "delta": m.delta, "reason": m.reason} for m in movements],
            "consent": consent,
            "audit_event_count": len(events),
            "audit_last_event": (events[-1].event_type if events else None),
        }
        report["provenance_sha256"] = hashlib.sha256(
            json.dumps(report, sort_keys=True, default=str).encode()).hexdigest()
        return report


# ======================================================================
# Outbox dispatch (Wave 9: idempotent consumer; Phase V: bounded retries + DLQ)
# ======================================================================

OUTBOX_MAX_ATTEMPTS = 5


def dispatch_outbox(limit: int = 20,
                    fault_injector: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Processes pending outbox events (topic 15).

    Honest semantics: there is no external message provider in this
    environment, so 'processing' records delivery state for observability;
    no external side effect is claimed. Duplicate delivery is assumed
    possible and handled idempotently (processed events are never re-claimed).

    Bounded retries + dead-letter (Phase V): a failing event is retried on
    later dispatches; after OUTBOX_MAX_ATTEMPTS it is dead-lettered — removed
    from the main queue with its error recorded for inspection/replay.
    `fault_injector(event_type)` is a test hook for deterministic failure
    injection (never set in production paths).
    """
    processed: List[Dict[str, Any]] = []
    dead_lettered: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    with session_scope() as session:
        pending = persistence.claim_pending_outbox(session, limit=limit)
        for ev in pending:
            try:
                if fault_injector is not None:
                    fault_injector(ev.event_type)
                # mark_outbox_processed increments attempts atomically on success
                persistence.mark_outbox_processed(session, ev.id)
                processed.append({"outbox_id": ev.id, "event_type": ev.event_type,
                                  "org_id": ev.org_id,
                                  "idempotency_key": ev.idempotency_key})
            except Exception as e:  # noqa: BLE001 — durable failure record
                ev.attempts += 1
                ev.last_error = str(e)[:500]
                if ev.attempts >= OUTBOX_MAX_ATTEMPTS:
                    # Dead-letter: stop redelivery, keep for inspection
                    ev.processed_at = _now()
                    ev.last_error = f"dead-lettered after {ev.attempts} attempts: {e}"
                    dead_lettered.append({"outbox_id": ev.id,
                                          "event_type": ev.event_type,
                                          "error": ev.last_error})
                else:
                    failed.append({"outbox_id": ev.id,
                                   "event_type": ev.event_type,
                                   "attempts": ev.attempts,
                                   "error": str(e)[:200]})
        session.flush()
    return {"processed": processed, "count": len(processed),
            "failed": failed, "dead_lettered": dead_lettered}
