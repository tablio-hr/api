from datetime import timedelta

from django.db import IntegrityError
from django.db.models import Max
from django.utils import timezone

from apps.identity.authorization import (
    AuthorizationContext,
    current_episode_for,
    is_current_interval,
)
from apps.identity.errors import ConflictDenied, LastAdminDenied, NotFoundDenied, StrongerRoleDenied
from apps.identity.login import normalize_primary_login
from apps.identity.models import (
    AssignmentStatus,
    LocationAssignment,
    MembershipEpisode,
    Role,
    RoleAssignment,
    RoleVersion,
    ScopeType,
    StaffMembership,
    UserIdentity,
)
from apps.tenants.models import BusinessLocation


def bump_generation(membership: StaffMembership) -> None:
    membership.authorization_generation += 1
    membership.save(update_fields=["authorization_generation", "updated_at"])


def lock_membership(*, tenant, public_id) -> StaffMembership:
    try:
        return (
            StaffMembership.objects.select_for_update()
            .select_related("user_identity", "tenant")
            .get(tenant=tenant, public_id=public_id)
        )
    except StaffMembership.DoesNotExist as exc:
        raise NotFoundDenied() from exc


def lock_tenant_memberships(tenant) -> list[StaffMembership]:
    return list(
        StaffMembership.objects.select_for_update()
        .select_related("user_identity", "tenant")
        .filter(tenant=tenant)
        .order_by("pk")
    )


def _membership_from_locked(locked: list[StaffMembership], public_id) -> StaffMembership:
    for row in locked:
        if str(row.public_id) == str(public_id):
            return row
    raise NotFoundDenied()


def create_staff_membership(
    authz: AuthorizationContext,
    *,
    name: str,
    primary_login: str,
    password: str,
    staff_number: str,
    invited: bool = False,
) -> dict:
    login = normalize_primary_login(primary_login)
    now = authz.now
    identity = UserIdentity.objects.filter(primary_login=login).first()
    if identity is None:
        identity = UserIdentity(name=name, primary_login=login, status=UserIdentity.Status.ACTIVE)
        identity.set_password(password)
        identity.save()
    if StaffMembership.objects.filter(tenant=authz.tenant, user_identity=identity).exists():
        raise ConflictDenied(code="conflict", detail="Conflict.")
    try:
        membership = StaffMembership.objects.create(
            tenant=authz.tenant,
            user_identity=identity,
            staff_number=staff_number,
        )
    except IntegrityError as exc:
        raise ConflictDenied(code="conflict", detail="Conflict.") from exc
    episode = MembershipEpisode.objects.create(
        tenant=authz.tenant,
        staff_membership=membership,
        version=1,
        status=MembershipEpisode.Status.INVITED if invited else MembershipEpisode.Status.ACTIVE,
        valid_from=now,
    )
    return membership_payload(membership, episode)


def activate_episode(authz: AuthorizationContext, *, membership_id) -> dict:
    now = authz.now
    membership = lock_membership(tenant=authz.tenant, public_id=membership_id)
    current = current_episode_for(membership)
    if current is not None and current.status == MembershipEpisode.Status.ACTIVE:
        if is_current_interval(now, current.valid_from, current.valid_until):
            return membership_payload(membership, current)
    if current is not None:
        current.status = MembershipEpisode.Status.ACTIVE
        current.save(update_fields=["status", "updated_at"])
        bump_generation(membership)
        return membership_payload(membership, current)
    max_version = (
        MembershipEpisode.objects.filter(staff_membership=membership).aggregate(Max("version"))[
            "version__max"
        ]
    )
    episode = MembershipEpisode.objects.create(
        tenant=authz.tenant,
        staff_membership=membership,
        version=1 if max_version is None else max_version + 1,
        status=MembershipEpisode.Status.ACTIVE,
        valid_from=now,
    )
    bump_generation(membership)
    return membership_payload(membership, episode)


def suspend_episode(authz: AuthorizationContext, *, membership_id) -> dict:
    now = authz.now
    locked = lock_tenant_memberships(authz.tenant)
    membership = _membership_from_locked(locked, membership_id)
    _assert_not_last_admin(locked, would_remove=membership, now=now)
    current = _require_current_episode(membership)
    if current.status != MembershipEpisode.Status.SUSPENDED:
        current.status = MembershipEpisode.Status.SUSPENDED
        current.save(update_fields=["status", "updated_at"])
        bump_generation(membership)
    return membership_payload(membership, current)


def end_episode(authz: AuthorizationContext, *, membership_id) -> dict:
    now = authz.now
    locked = lock_tenant_memberships(authz.tenant)
    membership = _membership_from_locked(locked, membership_id)
    _assert_not_last_admin(locked, would_remove=membership, now=now)
    current = _require_current_episode(membership)
    if current.status != MembershipEpisode.Status.ENDED:
        current.status = MembershipEpisode.Status.ENDED
        current.valid_until = _end_at(now, current.valid_from)
        current.save(update_fields=["status", "valid_until", "updated_at"])
        bump_generation(membership)
    return membership_payload(membership, current)


def add_location_assignment(
    authz: AuthorizationContext,
    *,
    membership_id,
    scope_type: str,
    location: BusinessLocation | None,
) -> dict:
    now = authz.now
    membership = lock_membership(tenant=authz.tenant, public_id=membership_id)
    episode = _require_current_episode(membership)
    assignment = LocationAssignment.objects.create(
        tenant=authz.tenant,
        staff_membership=membership,
        membership_episode=episode,
        scope_type=scope_type,
        location=location,
        status=AssignmentStatus.ACTIVE,
        valid_from=now,
    )
    bump_generation(membership)
    return location_assignment_payload(assignment)


def revoke_location_assignment(
    authz: AuthorizationContext,
    *,
    membership_id,
    assignment_id,
) -> dict:
    now = authz.now
    locked = lock_tenant_memberships(authz.tenant)
    membership = _membership_from_locked(locked, membership_id)
    try:
        assignment = LocationAssignment.objects.select_for_update().get(
            tenant=authz.tenant,
            staff_membership=membership,
            public_id=assignment_id,
        )
    except LocationAssignment.DoesNotExist as exc:
        raise NotFoundDenied() from exc
    if assignment.status == AssignmentStatus.ACTIVE and assignment.scope_type == ScopeType.TENANT:
        _assert_not_last_admin(locked, would_remove=membership, now=now)
    if assignment.status != AssignmentStatus.REVOKED:
        assignment.status = AssignmentStatus.REVOKED
        assignment.valid_until = _end_at(now, assignment.valid_from)
        assignment.save(update_fields=["status", "valid_until", "updated_at"])
        bump_generation(membership)
    return location_assignment_payload(assignment)


def add_role_assignment(
    authz: AuthorizationContext,
    *,
    membership_id,
    role_code: str,
    scope_type: str,
    location: BusinessLocation | None,
) -> dict:
    now = authz.now
    if role_code != Role.TENANT_ADMIN:
        raise ConflictDenied(code="invalid", detail="Unknown role.")
    role_version = (
        RoleVersion.objects.filter(role__code=role_code).select_related("role").order_by("-version").first()
    )
    if role_version is None:
        raise ConflictDenied(code="invalid", detail="Unknown role.")
    target_perms = set(role_version.permissions or [])
    if str(membership_id) == str(authz.membership.public_id) and not target_perms.issubset(authz.permissions):
        raise StrongerRoleDenied()
    membership = lock_membership(tenant=authz.tenant, public_id=membership_id)
    episode = _require_current_episode(membership)
    assignment = RoleAssignment.objects.create(
        tenant=authz.tenant,
        staff_membership=membership,
        membership_episode=episode,
        role_version=role_version,
        scope_type=scope_type,
        location=location,
        status=AssignmentStatus.ACTIVE,
        valid_from=now,
    )
    bump_generation(membership)
    return role_assignment_payload(assignment)


def revoke_role_assignment(
    authz: AuthorizationContext,
    *,
    membership_id,
    assignment_id,
) -> dict:
    now = authz.now
    locked = lock_tenant_memberships(authz.tenant)
    membership = _membership_from_locked(locked, membership_id)
    try:
        assignment = (
            RoleAssignment.objects.select_for_update()
            .select_related("role_version", "role_version__role")
            .get(tenant=authz.tenant, staff_membership=membership, public_id=assignment_id)
        )
    except RoleAssignment.DoesNotExist as exc:
        raise NotFoundDenied() from exc
    if (
        assignment.status == AssignmentStatus.ACTIVE
        and assignment.scope_type == ScopeType.TENANT
        and assignment.role_version.role.code == Role.TENANT_ADMIN
    ):
        _assert_not_last_admin(locked, would_remove=membership, now=now)
    if assignment.status != AssignmentStatus.REVOKED:
        assignment.status = AssignmentStatus.REVOKED
        assignment.valid_until = _end_at(now, assignment.valid_from)
        assignment.save(update_fields=["status", "valid_until", "updated_at"])
        bump_generation(membership)
    return role_assignment_payload(assignment)


def _require_current_episode(membership: StaffMembership) -> MembershipEpisode:
    current = current_episode_for(membership)
    if current is None:
        raise NotFoundDenied()
    return current


def _end_at(now, valid_from):
    if now > valid_from:
        return now
    return valid_from + timedelta(microseconds=1)


def _assert_not_last_admin(locked: list[StaffMembership], *, would_remove: StaffMembership, now) -> None:
    remaining = [row for row in locked if row.pk != would_remove.pk and _is_live_tenant_admin(row, now)]
    if not remaining:
        raise LastAdminDenied()


def _is_live_tenant_admin(membership: StaffMembership, now) -> bool:
    if membership.user_identity.status != UserIdentity.Status.ACTIVE:
        return False
    episode = current_episode_for(membership)
    if (
        episode is None
        or episode.status != MembershipEpisode.Status.ACTIVE
        or not is_current_interval(now, episode.valid_from, episode.valid_until)
    ):
        return False
    loc = LocationAssignment.objects.filter(
        staff_membership=membership,
        membership_episode=episode,
        scope_type=ScopeType.TENANT,
        status=AssignmentStatus.ACTIVE,
    )
    if not any(is_current_interval(now, row.valid_from, row.valid_until) for row in loc):
        return False
    roles = RoleAssignment.objects.filter(
        staff_membership=membership,
        membership_episode=episode,
        scope_type=ScopeType.TENANT,
        status=AssignmentStatus.ACTIVE,
        role_version__role__code=Role.TENANT_ADMIN,
    )
    return any(is_current_interval(now, row.valid_from, row.valid_until) for row in roles)


def membership_payload(membership: StaffMembership, episode: MembershipEpisode) -> dict:
    identity = membership.user_identity
    return {
        "id": str(membership.public_id),
        "staff_number": membership.staff_number,
        "authorization_generation": membership.authorization_generation,
        "identity": {
            "id": str(identity.public_id),
            "name": identity.name,
            "primary_login": identity.primary_login,
            "status": identity.status,
        },
        "episode": {
            "id": str(episode.public_id),
            "version": episode.version,
            "status": episode.status,
            "valid_from": episode.valid_from.isoformat(),
            "valid_until": episode.valid_until.isoformat() if episode.valid_until else None,
        },
    }


def location_assignment_payload(row: LocationAssignment) -> dict:
    return {
        "id": str(row.public_id),
        "scope_type": row.scope_type,
        "location_id": str(row.location.public_id) if row.location_id else None,
        "status": row.status,
        "valid_from": row.valid_from.isoformat(),
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
    }


def role_assignment_payload(row: RoleAssignment) -> dict:
    row.role_version.role  # ensure related if not loaded
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
