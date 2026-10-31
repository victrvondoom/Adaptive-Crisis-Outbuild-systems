"""
AIDNEXUS ONE — Database bootstrap: organizations, demo identities, inventory.

Seeds two independent organizations so multi-tenant isolation is real and
testable:
  - ORG-PACIFIC  (Pacific Relief Alliance)   — demo scenario seed=42
  - ORG-HIGHLAND (Highland Care Collective)  — demo scenario seed=777

Demo identities are SYNTHETIC (no real people, no PII) and exist only for the
development adapter. All emails are example.dev addresses.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .db import session_scope
from .models_db import Organization, User, Membership, Session as SessionRow, Depot
from . import persistence

logger = logging.getLogger("aidnexus.bootstrap")

ORG_PACIFIC = "ORG-PACIFIC"
ORG_HIGHLAND = "ORG-HIGHLAND"

# Synthetic demo identities: (email, name, role in PACIFIC, role in HIGHLAND)
DEMO_IDENTITIES = [
    ("platform-admin@example.dev", "Platform Admin (demo)", "PLATFORM_ADMIN", "PLATFORM_ADMIN"),
    ("ngo-admin@example.dev", "Ava Admin (demo)", "NGO_ADMIN", "NGO_ADMIN"),
    ("coordinator@example.dev", "Cora Coordinator (demo)", "MISSION_COORDINATOR", None),
    ("volunteer@example.dev", "Victor Volunteer (demo)", "FIELD_VOLUNTEER", None),
    ("auditor@example.dev", "Arden Auditor (demo)", "AUDITOR", None),
    ("observer@example.dev", "Olive Observer (demo)", "READ_ONLY_OBSERVER", None),
    ("rival-admin@example.dev", "Hana Admin (Highland)", None, "NGO_ADMIN"),
    ("rival-coordinator@example.dev", "Helena Coordinator (Highland)", None, "MISSION_COORDINATOR"),
]


def ensure_bootstrap() -> None:
    """Idempotent: creates orgs, users, memberships, depot inventory if absent."""
    with session_scope() as session:
        orgs = {}
        for org_id, name, slug in [
            (ORG_PACIFIC, "Pacific Relief Alliance", "pacific-relief"),
            (ORG_HIGHLAND, "Highland Care Collective", "highland-care"),
        ]:
            org = session.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()
            if org is None:
                org = Organization(id=org_id, name=name, slug=slug)
                session.add(org)
                session.flush()
            orgs[org_id] = org

        for email, name, pacific_role, highland_role in DEMO_IDENTITIES:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is None:
                user = User(id=f"USR-{uuid.uuid4().hex[:8]}", email=email, display_name=name,
                            is_platform_admin=email.startswith("platform-"))
                session.add(user)
                session.flush()
            for org_id, role in [(ORG_PACIFIC, pacific_role), (ORG_HIGHLAND, highland_role)]:
                if role is None:
                    continue
                existing = session.execute(select(Membership).where(
                    Membership.user_id == user.id, Membership.org_id == org_id)).scalar_one_or_none()
                if existing is None:
                    session.add(Membership(user_id=user.id, org_id=org_id, role=role))
        session.flush()

        # Depots + inventory per org (mirrors the in-memory scenario values).
        inventory_specs = {
            ORG_PACIFIC: {
                "DEPOT-ALPHA": {"lat": 14.6195, "lng": 120.9742, "sector": "Central Metro",
                                "inv": {"potable_water_liters": 15000.0, "trauma_kits": 400.0,
                                        "rations_mre": 5000.0, "hygiene_kits": 1200.0, "generators": 45.0}},
                "DEPOT-BRAVO": {"lat": 14.5495, "lng": 120.9442, "sector": "Coastal Port",
                                "inv": {"potable_water_liters": 20000.0, "trauma_kits": 250.0,
                                        "rations_mre": 8000.0, "hygiene_kits": 2000.0, "generators": 30.0}},
                "DEPOT-CHARLIE": {"lat": 14.6795, "lng": 121.0342, "sector": "Highland Foothills",
                                   "inv": {"potable_water_liters": 12000.0, "trauma_kits": 500.0,
                                           "rations_mre": 4500.0, "hygiene_kits": 900.0, "generators": 60.0}},
            },
            ORG_HIGHLAND: {
                "DEPOT-ALPHA": {"lat": 15.6195, "lng": 121.9742, "sector": "Northern Ridge",
                                "inv": {"potable_water_liters": 9000.0, "trauma_kits": 150.0,
                                        "rations_mre": 3000.0, "hygiene_kits": 600.0, "generators": 20.0}},
                "DEPOT-BRAVO": {"lat": 15.5495, "lng": 121.9442, "sector": "Delta Flats",
                                "inv": {"potable_water_liters": 11000.0, "trauma_kits": 120.0,
                                        "rations_mre": 3500.0, "hygiene_kits": 700.0, "generators": 15.0}},
                "DEPOT-CHARLIE": {"lat": 15.6795, "lng": 122.0342, "sector": "Upland Villages",
                                   "inv": {"potable_water_liters": 8000.0, "trauma_kits": 200.0,
                                           "rations_mre": 2500.0, "hygiene_kits": 500.0, "generators": 25.0}},
            },
        }
        for org_id, depots in inventory_specs.items():
            for depot_id, spec in depots.items():
                qualified = f"{org_id}:{depot_id}"
                exists = session.get(Depot, qualified)
                if exists is None:
                    session.add(Depot(id=qualified, org_id=org_id,
                                      name=depot_id.replace("DEPOT-", "").title() + " Hub",
                                      lat=spec["lat"], lng=spec["lng"], sector=spec["sector"],
                                      status="OPERATIONAL"))
                    session.flush()
                for item_type, qty in spec["inv"].items():
                    persistence.seed_inventory(session, org_id=org_id, depot_id=depot_id,
                                               item_type=item_type, quantity=qty)
        # Volunteers per org (mirrors the engine's scenario roster) so
        # certification-expiry tracking has durable records.
        from .models_db import VolunteerRow
        roles = ["Paramedic Lead", "Heavy Logistics Driver", "Emergency Nurse", "Disaster Specialist"]
        for org_id in (ORG_PACIFIC, ORG_HIGHLAND):
            for i in range(1, 13):
                vid = f"{org_id}:VOL-{i:02d}"  # org-qualified PK
                exists = session.execute(select(VolunteerRow).where(
                    VolunteerRow.org_id == org_id,
                    VolunteerRow.id == vid)).scalar_one_or_none()
                if exists is None:
                    session.add(VolunteerRow(id=vid, org_id=org_id,
                                              name=f"Volunteer Specialist {i:02d}",
                                              role=roles[(i - 1) % len(roles)],
                                              status="AVAILABLE"))
        session.flush()
    logger.info("bootstrap ensured (orgs, demo identities, inventory, volunteers)")


def create_dev_session(user_id: str, ttl_hours: int = 8) -> str:
    """Creates a revocable session row and returns its jti."""
    jti = uuid.uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    with session_scope() as session:
        persistence.create_session(session, jti=jti, user_id=user_id, expires_at=expires)
    return jti


def get_memberships_for_user(user_id: str) -> list:
    """Membership-derived org scopes (authoritative tenant source)."""
    with session_scope() as session:
        rows = session.execute(select(Membership).where(
            Membership.user_id == user_id,
            Membership.revoked_at.is_(None))).scalars().all()
        return [{"org_id": r.org_id, "role": r.role} for r in rows]
