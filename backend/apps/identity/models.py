import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models.functions import Lower

from apps.identity.login import normalize_primary_login
from apps.tenants.models import BusinessLocation, Tenant


class UserIdentity(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        LOCKED = "locked", "Locked"
        DISABLED = "disabled", "Disabled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    primary_login = models.CharField(max_length=254)
    password = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["primary_login"]
        constraints = [
            models.UniqueConstraint(Lower("primary_login"), name="identity_user_unique_login_lower"),
        ]

    def __str__(self) -> str:
        return self.primary_login

    def save(self, *args, **kwargs):
        self.primary_login = normalize_primary_login(self.primary_login)
        super().save(*args, **kwargs)

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)


class StaffMembership(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="staff_memberships")
    user_identity = models.ForeignKey(
        UserIdentity,
        on_delete=models.PROTECT,
        related_name="staff_memberships",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    staff_number = models.CharField(max_length=32)
    authorization_generation = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant_id", "staff_number"]
        constraints = [
            models.UniqueConstraint(fields=["id", "tenant"], name="identity_membership_unique_id_tenant"),
            models.UniqueConstraint(
                fields=["tenant", "user_identity"],
                name="identity_membership_unique_tenant_identity",
            ),
            models.UniqueConstraint(
                fields=["tenant", "staff_number"],
                name="identity_membership_unique_tenant_staff_number",
            ),
            models.CheckConstraint(
                condition=models.Q(authorization_generation__gte=0),
                name="identity_membership_generation_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_identity_id} @ {self.tenant_id}"


class MembershipEpisode(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ENDED = "ended", "Ended"

    CURRENT_STATUSES = (Status.INVITED, Status.ACTIVE, Status.SUSPENDED)

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="membership_episodes")
    staff_membership = models.ForeignKey(
        StaffMembership,
        on_delete=models.PROTECT,
        related_name="episodes",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["staff_membership_id", "version"]
        constraints = [
            models.UniqueConstraint(fields=["id", "tenant"], name="identity_episode_unique_id_tenant"),
            models.UniqueConstraint(
                fields=["id", "staff_membership", "tenant"],
                name="identity_episode_unique_id_membership_tenant",
            ),
            models.UniqueConstraint(
                fields=["staff_membership", "version"],
                name="identity_episode_unique_membership_version",
            ),
            models.UniqueConstraint(
                fields=["staff_membership"],
                condition=models.Q(status__in=["invited", "active", "suspended"]),
                name="identity_episode_one_current",
            ),
            models.CheckConstraint(condition=models.Q(version__gt=0), name="identity_episode_version_gt_0"),
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=models.F("valid_from")),
                name="identity_episode_valid_interval",
            ),
        ]

    def __str__(self) -> str:
        return f"episode {self.version} ({self.status})"


class AssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"


class ScopeType(models.TextChoices):
    TENANT = "tenant", "Tenant"
    LOCATION = "location", "Location"


class LocationAssignment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="location_assignments")
    staff_membership = models.ForeignKey(
        StaffMembership,
        on_delete=models.PROTECT,
        related_name="location_assignments",
    )
    membership_episode = models.ForeignKey(
        MembershipEpisode,
        on_delete=models.PROTECT,
        related_name="location_assignments",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    location = models.ForeignKey(
        BusinessLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="location_assignments",
    )
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.ACTIVE)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["staff_membership_id", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(scope_type=ScopeType.TENANT) & models.Q(location__isnull=True))
                    | (models.Q(scope_type=ScopeType.LOCATION) & models.Q(location__isnull=False))
                ),
                name="identity_loc_assign_scope_location",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=models.F("valid_from")),
                name="identity_loc_assign_valid_interval",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scope_type} assignment {self.public_id}"


class Role(models.Model):
    TENANT_ADMIN = "TENANT_ADMIN"

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    is_system = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class RoleVersion(models.Model):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    permissions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role_id", "version"]
        constraints = [
            models.UniqueConstraint(fields=["role", "version"], name="identity_roleversion_unique_role_version"),
            models.CheckConstraint(condition=models.Q(version__gt=0), name="identity_roleversion_version_gt_0"),
        ]

    def __str__(self) -> str:
        return f"{self.role_id} v{self.version}"


class RoleAssignment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="role_assignments")
    staff_membership = models.ForeignKey(
        StaffMembership,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    membership_episode = models.ForeignKey(
        MembershipEpisode,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role_version = models.ForeignKey(
        RoleVersion,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    location = models.ForeignKey(
        BusinessLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="role_assignments",
    )
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.ACTIVE)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["staff_membership_id", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(scope_type=ScopeType.TENANT) & models.Q(location__isnull=True))
                    | (models.Q(scope_type=ScopeType.LOCATION) & models.Q(location__isnull=False))
                ),
                name="identity_role_assign_scope_location",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=models.F("valid_from")),
                name="identity_role_assign_valid_interval",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role_version_id} @ {self.staff_membership_id}"


class StaffAccessSession(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="staff_access_sessions")
    staff_membership = models.ForeignKey(
        StaffMembership,
        on_delete=models.PROTECT,
        related_name="access_sessions",
    )
    membership_episode = models.ForeignKey(
        MembershipEpisode,
        on_delete=models.PROTECT,
        related_name="access_sessions",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    authorization_generation = models.PositiveIntegerField()
    token_prefix = models.CharField(max_length=32)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["id", "tenant"], name="identity_session_unique_id_tenant"),
            models.UniqueConstraint(
                fields=["id", "staff_membership", "tenant"],
                name="identity_session_unique_id_membership_tenant",
            ),
        ]

    def __str__(self) -> str:
        return self.token_prefix
