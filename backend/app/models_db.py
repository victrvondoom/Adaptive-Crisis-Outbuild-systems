"""
AIDNEXUS ONE — Relational models (SQLAlchemy 2.0).

Multi-tenant core: every business row carries org_id with an FK to
organizations; repositories enforce tenant scoping on top of it.

Key invariants encoded here (defense in depth — not only in app code):
- delivery receipts: one per request (UNIQUE) → double confirmation impossible
- inventory movements: unique idempotency key → duplicate events rejected
- audit events: UNIQUE(org_id, seq) and UNIQUE(org_id, sha256) → chain integrity
- memberships: UNIQUE(user_id, org_id)
"""
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import (String, Integer, Float, Boolean, ForeignKey, UniqueConstraint, CheckConstraint,
                         Index, Text, DateTime, BigInteger, JSON)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now():
    return datetime.now(timezone.utc)


def _uid(n=12):
    return uuid.uuid4().hex[:n]


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _uid(10))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _uid(10))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: _uid(10))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)


class Session(Base):
    """Revocable sessions: a token is only valid while its session row is live."""
    __tablename__ = "sessions"
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Depot(Base):
    __tablename__ = "depots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    sector: Mapped[str] = mapped_column(String(100), default="Central")
    status: Mapped[str] = mapped_column(String(32), default="OPERATIONAL")
    __table_args__ = (UniqueConstraint("org_id", "id", name="uq_depot_org_id"),)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    depot_id: Mapped[str] = mapped_column(ForeignKey("depots.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("depot_id", "item_type", name="uq_inventory_depot_item"),
                      Index("ix_inventory_org_type", "org_id", "item_type"),
                      # DB-enforced invariant: stock can never go negative,
                      # regardless of application bugs.
                      CheckConstraint("quantity >= 0", name="ck_inventory_nonnegative"))


class InventoryMovement(Base):
    """Every inventory change is an append-only ledger row with an idempotency key."""
    __tablename__ = "inventory_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    depot_id: Mapped[str] = mapped_column(ForeignKey("depots.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)  # DELIVERY|REPLAN|SEED|CORRECTION
    request_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AidRequestRow(Base):
    __tablename__ = "aid_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_name: Mapped[str] = mapped_column(String(200), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    sector: Mapped[str] = mapped_column(String(100), default="Central")
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    deadline_hours: Mapped[float] = mapped_column(Float, default=24.0)
    affected_people: Mapped[int] = mapped_column(Integer, default=10)
    urgency_score: Mapped[float] = mapped_column(Float, default=75.0)
    duplicate_of_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intake_channel: Mapped[str] = mapped_column(String(32), default="MANUAL")
    special_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    delivered_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    items: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (Index("ix_requests_org_status", "org_id", "status"),)


class VehicleRow(Base):
    __tablename__ = "vehicles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    base_depot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="IDLE")
    speed_kmh: Mapped[float] = mapped_column(Float, default=45.0)


class VolunteerRow(Base):
    __tablename__ = "volunteers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="AVAILABLE")
    assigned_vehicle_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    certification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseNoteRow(Base):
    __tablename__ = "case_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ApprovalDelegationRow(Base):
    __tablename__ = "approval_delegations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    delegator_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    delegate_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    permission: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PlanVersionRow(Base):
    __tablename__ = "plan_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(32), nullable=False)
    optimization_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # full plan snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("org_id", "version_id", name="uq_plan_org_version"),)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_row_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id"), nullable=False)
    # Approver identity: a verified user id when a human approved, or a
    # system label (e.g. SYSTEM_BOOTSTRAP) recorded verbatim.
    approver: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # APPROVED|REJECTED|AUTO_ACTIVATED
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DeliveryReceiptRow(Base):
    __tablename__ = "delivery_receipts"
    request_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    volunteer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class DisruptionRow(Base):
    __tablename__ = "disruptions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    hazard_radius_km: Mapped[float] = mapped_column(Float, default=3.5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEventRow(Base):
    """Tamper-evident, org-scoped hash chain. Note the honest claim: the chain
    makes the log tamper-EVIDENT (modifying a row breaks subsequent hashes and
    the seq/prev-hash verification); it does not make the table immutable."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("org_id", "seq", name="uq_audit_org_seq"),
                      UniqueConstraint("org_id", "sha256", name="uq_audit_org_hash"))


class AgentExecutionRow(Base):
    __tablename__ = "agent_executions"
    id: Mapped[str] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # SUCCEEDED|FAILED|REVIEW_REQUIRED
    provider: Mapped[str] = mapped_column(String(64), default="deterministic")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), default="")
    context_version: Mapped[str] = mapped_column(String(32), default="")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    postcondition_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentToolCallRow(Base):
    __tablename__ = "agent_tool_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_row_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="OK")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OutboxEventRow(Base):
    """Transactional outbox: business transaction commits the event row in the
    same DB transaction; a worker delivers it to external systems idempotently."""
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
