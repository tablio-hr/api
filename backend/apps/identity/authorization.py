from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from apps.identity.models import (
    AssignmentStatus,
    LocationAssignment,
    MembershipEpisode,
    RoleAssignment,
    ScopeType,
    StaffAccessSession,
    StaffMembership,
    UserIdentity,
)
from apps.tenants.models import BusinessLocation, Tenant


class AuthorizeDenied(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AuthorizationContext:
    session: StaffAccessSession
    identity: UserIdentity
    tenant: Tenant
    membership: StaffMembership
    episode: MembershipEpisode
    location_assignments: list[LocationAssignment]
    role_assignments: list[RoleAssignment]
    permissions: frozenset[str]
    now: datetime


def is_current_interval(now, valid_from, valid_until) -> bool:
    if valid_from > now:
        return False
    if valid_until is not None and valid_until <= now:
        return False
    return True


def current_episode_for(membership: StaffMembership) -> MembershipEpisode | None:
    return (
        MembershipEpisode.objects.filter(
            staff_membership=membership,
            status__in=MembershipEpisode.CURRENT_STATUSES,
        )
        .order_by("version")
        .first()
    )


def authorize(
    *,
    session: StaffAccessSession,
    permission: str | None = None,
    location: BusinessLocation | None = None,
    require_active_location: bool = False,
    now=None,
) -> AuthorizationContext:
    now = now or timezone.now()
    membership = session.staff_membership
    identity = membership.user_identity
    tenant = session.tenant
    bound_episode = session.membership_episode

    if session.revoked_at is not None or session.expires_at <= now:
        raise AuthorizeDenied(401, "not_authenticated", "Authentication required.")
    if tenant.status != Tenant.Status.ACTIVE:
        raise AuthorizeDenied(404, "not_found", "Not found.")
    if identity.status != UserIdentity.Status.ACTIVE:
        raise AuthorizeDenied(403, "forbidden", "Forbidden.")
    if session.authorization_generation != membership.authorization_generation:
        raise AuthorizeDenied(401, "not_authenticated", "Authentication required.")

    live = current_episode_for(membership)
    if live is None:
        if bound_episode.status == MembershipEpisode.Status.ENDED or not is_current_interval(
            now, bound_episode.valid_from, bound_episode.valid_until
        ):
            raise AuthorizeDenied(403, "forbidden", "Forbidden.")
        raise AuthorizeDenied(401, "not_authenticated", "Authentication required.")
    if live.pk != session.membership_episode_id:
        raise AuthorizeDenied(401, "not_authenticated", "Authentication required.")
    if live.status != MembershipEpisode.Status.ACTIVE or not is_current_interval(
        now, live.valid_from, live.valid_until
    ):
        raise AuthorizeDenied(403, "forbidden", "Forbidden.")

    if location is not None and location.tenant_id != session.tenant_id:
        raise AuthorizeDenied(403, "forbidden", "Forbidden.")
    if require_active_location and location is not None and not location.is_active:
        raise AuthorizeDenied(403, "forbidden", "Forbidden.")

    location_assignments = _live_assignments(
        LocationAssignment.objects.filter(
            membership_episode=live,
            staff_membership=membership,
            tenant=tenant,
        ).select_related("location"),
        now,
    )
    role_assignments = _live_assignments(
        RoleAssignment.objects.filter(
            membership_episode=live,
            staff_membership=membership,
            tenant=tenant,
        ).select_related("role_version", "role_version__role", "location"),
        now,
    )
    covering = [row for row in location_assignments if _covers_target(row, location)]
    granted = _permissions_for(role_assignments, covering, location)

    if permission is not None:
        if location is None and not any(row.scope_type == ScopeType.TENANT for row in covering):
            raise AuthorizeDenied(403, "forbidden", "Forbidden.")
        if location is not None and not covering:
            raise AuthorizeDenied(403, "forbidden", "Forbidden.")
        if permission not in granted:
            raise AuthorizeDenied(403, "forbidden", "Forbidden.")

    return AuthorizationContext(
        session=session,
        identity=identity,
        tenant=tenant,
        membership=membership,
        episode=live,
        location_assignments=location_assignments,
        role_assignments=role_assignments,
        permissions=granted,
        now=now,
    )


def context_payload(authz: AuthorizationContext) -> dict:
    tenant_permissions = _permissions_for(
        authz.role_assignments,
        [row for row in authz.location_assignments if row.scope_type == ScopeType.TENANT],
        None,
    )
    return {
        "identity": {
            "id": str(authz.identity.public_id),
            "name": authz.identity.name,
            "primary_login": authz.identity.primary_login,
            "status": authz.identity.status,
        },
        "tenant": {
            "id": str(authz.tenant.public_id),
            "name": authz.tenant.name,
            "slug": authz.tenant.slug,
            "status": authz.tenant.status,
        },
        "membership": {
            "id": str(authz.membership.public_id),
            "staff_number": authz.membership.staff_number,
            "authorization_generation": authz.membership.authorization_generation,
        },
        "episode": {
            "id": str(authz.episode.public_id),
            "version": authz.episode.version,
            "status": authz.episode.status,
            "valid_from": authz.episode.valid_from.isoformat(),
            "valid_until": authz.episode.valid_until.isoformat() if authz.episode.valid_until else None,
        },
        "location_assignments": [_location_assignment_payload(row) for row in authz.location_assignments],
        "role_assignments": [_role_assignment_payload(row) for row in authz.role_assignments],
        "permissions": sorted(tenant_permissions),
    }


def _live_assignments(qs, now):
    return [
        row
        for row in qs
        if row.status == AssignmentStatus.ACTIVE
        and is_current_interval(now, row.valid_from, row.valid_until)
    ]


def _covers_target(assignment: LocationAssignment, location: BusinessLocation | None) -> bool:
    if assignment.scope_type == ScopeType.TENANT:
        return True
    return location is not None and assignment.location_id == location.pk


def _role_intersects(
    role_assignment: RoleAssignment,
    covering: list[LocationAssignment],
    location: BusinessLocation | None,
) -> bool:
    if not covering:
        return False
    if role_assignment.scope_type == ScopeType.TENANT:
        return True
    if location is None:
        return False
    return role_assignment.location_id == location.pk


def _permissions_for(
    role_assignments: list[RoleAssignment],
    covering: list[LocationAssignment],
    location: BusinessLocation | None,
) -> frozenset[str]:
    granted: set[str] = set()
    for role_assignment in role_assignments:
        if not _role_intersects(role_assignment, covering, location):
            continue
        granted.update(role_assignment.role_version.permissions or [])
    return frozenset(granted)


def _location_assignment_payload(row: LocationAssignment) -> dict:
    return {
        "id": str(row.public_id),
        "scope_type": row.scope_type,
        "location_id": str(row.location.public_id) if row.location_id else None,
        "status": row.status,
        "valid_from": row.valid_from.isoformat(),
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
    }


def _role_assignment_payload(row: RoleAssignment) -> dict:
    return {
        "id": str(row.public_id),
        "role": row.role_version.role.code,
        "role_version": row.role_version.version,
        "scope_type": row.scope_type,
        "location_id": str(row.location.public_id) if row.location_id else None,
        "permissions": sorted(row.role_version.permissions or []),
        "status": row.status,
        "valid_from": row.valid_from.isoformat(),
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
    }
