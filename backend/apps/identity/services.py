import secrets
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

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
from apps.identity.permissions import TENANT_ADMIN_PERMISSIONS
from apps.tenants.models import Tenant
from apps.tenants.services import get_or_create_business_location

STAGE_TENANTS = (
    {
        "slug": "sibenik-1983",
        "name": "ŠIBENIK 1983 j.d.o.o.",
        "timezone": "Europe/Zagreb",
        "admin_name": "Natalija Radić",
        "admin_login": "mozartsibenik@gmail.com",
        "password_env": "SEED_ADMIN_PASSWORD_SIBENIK_1983",
        "locations": ("Caffe Bar Mozart", "Dvorana Baldekin"),
    },
    {
        "slug": "supina-poljica",
        "name": "ŠUPINA POLJICA j.d.o.o.",
        "timezone": "Europe/Zagreb",
        "admin_name": "Toni Šupe",
        "admin_login": "tonisupe7@gmail.com",
        "password_env": "SEED_ADMIN_PASSWORD_SUPINA_POLJICA",
        "locations": ("Restaurant Uzorita",),
    },
)


def ensure_system_roles() -> RoleVersion:
    role, _ = Role.objects.get_or_create(
        code=Role.TENANT_ADMIN,
        defaults={"name": "Tenant administrator", "is_system": True},
    )
    version, _ = RoleVersion.objects.get_or_create(
        role=role,
        version=1,
        defaults={"permissions": sorted(TENANT_ADMIN_PERMISSIONS)},
    )
    return version


@dataclass(frozen=True)
class BootstrapResult:
    tenant: Tenant
    identity: UserIdentity
    membership: StaffMembership
    episode: MembershipEpisode
    created_tenant: bool
    password_set: bool
    generated_password: str | None


@transaction.atomic
def bootstrap_tenant(
    *,
    slug: str,
    name: str,
    timezone_name: str,
    admin_login: str,
    admin_name: str,
    admin_password: str | None,
    location_names: tuple[str, ...] | list[str],
    staff_number: str = "1",
    reset_admin_password: bool = False,
) -> BootstrapResult:
    role_version = ensure_system_roles()
    now = timezone.now()
    login = normalize_primary_login(admin_login)

    tenant, created_tenant = Tenant.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "timezone": timezone_name, "status": Tenant.Status.ACTIVE},
    )

    identity = UserIdentity.objects.filter(primary_login=login).first()
    generated_password = None
    password_set = False
    if identity is None:
        raw = admin_password or secrets.token_urlsafe(24)
        generated_password = None if admin_password else raw
        identity = UserIdentity(name=admin_name, primary_login=login, status=UserIdentity.Status.ACTIVE)
        identity.set_password(raw)
        identity.save()
        password_set = True
    elif reset_admin_password:
        raw = admin_password or secrets.token_urlsafe(24)
        generated_password = None if admin_password else raw
        identity.set_password(raw)
        identity.name = admin_name
        identity.save(update_fields=["password", "name", "updated_at"])
        password_set = True

    membership, _ = StaffMembership.objects.get_or_create(
        tenant=tenant,
        user_identity=identity,
        defaults={"staff_number": staff_number},
    )

    episode = (
        MembershipEpisode.objects.filter(
            staff_membership=membership,
            status__in=MembershipEpisode.CURRENT_STATUSES,
        )
        .order_by("version")
        .first()
    )
    if episode is None:
        episode = MembershipEpisode.objects.create(
            tenant=tenant,
            staff_membership=membership,
            version=1,
            status=MembershipEpisode.Status.ACTIVE,
            valid_from=now,
        )

    for location_name in location_names:
        get_or_create_business_location(
            tenant=tenant,
            name=location_name,
            timezone=timezone_name,
        )

    LocationAssignment.objects.get_or_create(
        tenant=tenant,
        staff_membership=membership,
        membership_episode=episode,
        scope_type=ScopeType.TENANT,
        location=None,
        defaults={
            "status": AssignmentStatus.ACTIVE,
            "valid_from": now,
        },
    )
    RoleAssignment.objects.get_or_create(
        tenant=tenant,
        staff_membership=membership,
        membership_episode=episode,
        role_version=role_version,
        scope_type=ScopeType.TENANT,
        location=None,
        defaults={
            "status": AssignmentStatus.ACTIVE,
            "valid_from": now,
        },
    )

    return BootstrapResult(
        tenant=tenant,
        identity=identity,
        membership=membership,
        episode=episode,
        created_tenant=created_tenant,
        password_set=password_set,
        generated_password=generated_password,
    )


def seed_stage_tenants(*, passwords: dict[str, str | None], reset_admin_password: bool = False) -> list[BootstrapResult]:
    results = []
    for spec in STAGE_TENANTS:
        results.append(
            bootstrap_tenant(
                slug=spec["slug"],
                name=spec["name"],
                timezone_name=spec["timezone"],
                admin_login=spec["admin_login"],
                admin_name=spec["admin_name"],
                admin_password=passwords.get(spec["password_env"]),
                location_names=spec["locations"],
                reset_admin_password=reset_admin_password,
            )
        )
    return results
