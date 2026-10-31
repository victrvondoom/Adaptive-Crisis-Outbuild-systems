"""
AIDNEXUS ONE — Roles, permission matrix, and authorization decisions.

Tenant access is ALWAYS derived from the verified identity's membership
records. A client-supplied org_id is only accepted as the *selection* of one
of the identity's own orgs; a mismatch is rejected with 403.
"""
from enum import Enum
from typing import Optional, List


class Role(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    NGO_ADMIN = "NGO_ADMIN"
    MISSION_COORDINATOR = "MISSION_COORDINATOR"
    FIELD_VOLUNTEER = "FIELD_VOLUNTEER"
    AUDITOR = "AUDITOR"
    READ_ONLY_OBSERVER = "READ_ONLY_OBSERVER"


class Permission(str, Enum):
    READ_ORG_DATA = "READ_ORG_DATA"
    CREATE_REQUEST = "CREATE_REQUEST"
    TRANSITION_MISSION = "TRANSITION_MISSION"
    RUN_OPTIMIZATION = "RUN_OPTIMIZATION"
    INJECT_DISRUPTION = "INJECT_DISRUPTION"
    APPROVE_PLAN = "APPROVE_PLAN"
    CONFIRM_DELIVERY = "CONFIRM_DELIVERY"
    SIM_CONTROL = "SIM_CONTROL"
    AUDIT_READ = "AUDIT_READ"
    MANAGE_MEMBERS = "MANAGE_MEMBERS"
    EXPORT_DATA = "EXPORT_DATA"
    DELETE_DATA = "DELETE_DATA"
    PLATFORM_OPERATIONS = "PLATFORM_OPERATIONS"


# The permission matrix: role -> allowed permissions within that org.
PERMISSION_MATRIX = {
    Role.PLATFORM_ADMIN: [p for p in Permission],
    Role.NGO_ADMIN: [
        Permission.READ_ORG_DATA, Permission.CREATE_REQUEST, Permission.TRANSITION_MISSION,
        Permission.RUN_OPTIMIZATION, Permission.INJECT_DISRUPTION, Permission.APPROVE_PLAN,
        Permission.CONFIRM_DELIVERY, Permission.SIM_CONTROL, Permission.AUDIT_READ,
        Permission.MANAGE_MEMBERS, Permission.EXPORT_DATA, Permission.DELETE_DATA,
    ],
    Permission: [],  # placeholder never used
    Role.MISSION_COORDINATOR: [
        Permission.READ_ORG_DATA, Permission.CREATE_REQUEST, Permission.TRANSITION_MISSION,
        Permission.RUN_OPTIMIZATION, Permission.INJECT_DISRUPTION, Permission.APPROVE_PLAN,
        Permission.SIM_CONTROL, Permission.AUDIT_READ,
    ],
    Role.FIELD_VOLUNTEER: [
        Permission.READ_ORG_DATA, Permission.CONFIRM_DELIVERY,
    ],
    Role.AUDITOR: [
        Permission.READ_ORG_DATA, Permission.AUDIT_READ, Permission.EXPORT_DATA,
    ],
    Role.READ_ONLY_OBSERVER: [
        Permission.READ_ORG_DATA,
    ],
}
PERMISSION_MATRIX.pop(Permission)  # remove placeholder

WRITE_BLOCKED_FOR = {Role.AUDITOR, Role.READ_ONLY_OBSERVER}


class AuthorizationError(Exception):
    """Raised when the identity lacks permission or tenant scope. 403."""


def role_has_permission(role: str, permission: Permission) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return permission in PERMISSION_MATRIX.get(r, [])


def resolve_org_scope(identity, requested_org_id: Optional[str]) -> str:
    """Resolves the org this request operates on.

    Rules:
    - requested org must be one of the identity's orgs (membership-derived).
    - if not specified, the identity's single org is used; ambiguous otherwise.
    - PLATFORM_ADMIN may access any org (audited by the caller) — including
      orgs outside their membership list, since platform administration is
      their function.
    """
    org_ids = identity.org_ids()
    if requested_org_id is None:
        if len(org_ids) == 1:
            return org_ids[0]
        if identity.is_platform_admin:
            raise AuthorizationError("org_id required (multiple scopes / platform admin)")
        raise AuthorizationError("org_id required")
    if requested_org_id in org_ids:
        return requested_org_id
    if identity.is_platform_admin:
        return requested_org_id
    raise AuthorizationError(f"no access to organization {requested_org_id}")


def require_permission(identity, org_id: str, permission: Permission) -> str:
    """Returns the role used, or raises AuthorizationError (fail closed)."""
    role = identity.role_in(org_id)
    if role is None and identity.is_platform_admin:
        role = Role.PLATFORM_ADMIN.value
    if role is None:
        raise AuthorizationError(f"no membership in organization {org_id}")
    if not role_has_permission(role, permission):
        raise AuthorizationError(f"role {role} lacks permission {permission.value}")
    return role
