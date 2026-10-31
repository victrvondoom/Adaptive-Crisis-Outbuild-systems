"""Phase III feature persistence: expiry tracking, certification expiry,
case notes, approval delegations. Tenant-scoped like persistence.py."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update

from .db import session_scope
from .models_db import (InventoryItem, VolunteerRow, CaseNoteRow,
                        ApprovalDelegationRow)
from .persistence import q_depot, q_req


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# -- Inventory expiry (INV-006) ------------------------------------------
def set_inventory_expiry(org_id, depot_id, item_type, expires_at) -> bool:
    with session_scope() as s:
        res = s.execute(update(InventoryItem)
                        .where(InventoryItem.depot_id == q_depot(org_id, depot_id),
                               InventoryItem.item_type == item_type)
                        .values(expires_at=expires_at))
        return res.rowcount > 0


def expiring_inventory(org_id, within_days: int = 30):
    """Items expiring within the window, or already expired (risk report)."""
    with session_scope() as s:
        horizon = datetime.now(timezone.utc) + timedelta(days=within_days)
        rows = s.execute(select(InventoryItem).where(
            InventoryItem.org_id == org_id,
            InventoryItem.expires_at.is_not(None))).scalars().all()
        out = []
        now = datetime.now(timezone.utc)
        for r in rows:
            exp = _aware(r.expires_at)
            if exp <= horizon:
                out.append({"depot_id": r.depot_id, "item_type": r.item_type,
                            "quantity": r.quantity, "expires_at": exp.isoformat(),
                            "already_expired": exp <= now})
        out.sort(key=lambda x: x["expires_at"])
        return out


# -- Volunteer certification expiry (VOL-011) -----------------------------
def set_volunteer_certification(org_id, volunteer_id, expires_at) -> bool:
    with session_scope() as s:
        res = s.execute(update(VolunteerRow)
                        .where(VolunteerRow.org_id == org_id,
                               VolunteerRow.id == f"{org_id}:{volunteer_id}")
                        .values(certification_expires_at=expires_at))
        return res.rowcount > 0


def volunteers_with_expired_certification(org_id):
    with session_scope() as s:
        rows = s.execute(select(VolunteerRow).where(
            VolunteerRow.org_id == org_id,
            VolunteerRow.certification_expires_at.is_not(None))).scalars().all()
        now = datetime.now(timezone.utc)
        return [{"volunteer_id": r.id.split(":", 1)[1] if ":" in r.id else r.id,
                 "name": r.name,
                 "expired_at": _aware(r.certification_expires_at).isoformat()}
                for r in rows if _aware(r.certification_expires_at) <= now]


# -- Case notes (TRI-011) --------------------------------------------------
def add_case_note(org_id, request_id, author_user_id, note) -> dict:
    with session_scope() as s:
        row = CaseNoteRow(org_id=org_id, request_id=q_req(org_id, request_id),
                          author_user_id=author_user_id, note=note)
        s.add(row)
        s.flush()
        return {"id": row.id, "author_user_id": author_user_id, "note": note,
                "created_at": row.created_at.isoformat()}


def list_case_notes(org_id, request_id) -> list:
    with session_scope() as s:
        rows = s.execute(select(CaseNoteRow).where(
            CaseNoteRow.org_id == org_id,
            CaseNoteRow.request_id == q_req(org_id, request_id))
            .order_by(CaseNoteRow.id)).scalars().all()
        return [{"id": r.id, "author_user_id": r.author_user_id, "note": r.note,
                 "created_at": r.created_at.isoformat()} for r in rows]


# -- Approval delegations (APR-006) ----------------------------------------
def create_delegation(org_id, delegator_user_id, delegate_user_id,
                      permission, expires_at) -> dict:
    with session_scope() as s:
        row = ApprovalDelegationRow(org_id=org_id, delegator_user_id=delegator_user_id,
                                    delegate_user_id=delegate_user_id,
                                    permission=permission, expires_at=expires_at)
        s.add(row)
        s.flush()
        return {"id": row.id, "delegate_user_id": delegate_user_id,
                "permission": permission}


def has_active_delegation(org_id, delegate_user_id, permission) -> bool:
    with session_scope() as s:
        rows = s.execute(select(ApprovalDelegationRow).where(
            ApprovalDelegationRow.org_id == org_id,
            ApprovalDelegationRow.delegate_user_id == delegate_user_id,
            ApprovalDelegationRow.permission == permission,
            ApprovalDelegationRow.revoked_at.is_(None))).scalars().all()
        now = datetime.now(timezone.utc)
        return any(_aware(r.expires_at) > now for r in rows)


def revoke_delegations(org_id, delegate_user_id) -> int:
    with session_scope() as s:
        rows = s.execute(select(ApprovalDelegationRow).where(
            ApprovalDelegationRow.org_id == org_id,
            ApprovalDelegationRow.delegate_user_id == delegate_user_id,
            ApprovalDelegationRow.revoked_at.is_(None))).scalars().all()
        for r in rows:
            r.revoked_at = datetime.now(timezone.utc)
        return len(rows)
