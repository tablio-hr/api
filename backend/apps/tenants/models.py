import uuid

from django.db import models
from django.db.models.functions import Lower

from apps.tenants.tokens import default_key_prefix, display_prefix, generate_token, hash_token

VALID_SCOPES = frozenset({"public:read", "admin:read", "admin:write"})


class OperatorTenantManager(models.Manager):
    """Unscoped operator/platform lookup. Not for tenant API request paths."""


class Tenant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    timezone = models.CharField(max_length=64, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    operator_objects = OperatorTenantManager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class TenantDomain(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain"]

    def __str__(self) -> str:
        return self.domain


class BusinessLocation(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="locations")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["id", "tenant"], name="tenants_location_unique_id_tenant"),
            models.UniqueConstraint(fields=["tenant", "public_id"], name="tenants_location_unique_tenant_public"),
            models.UniqueConstraint(Lower("name"), "tenant", name="tenants_location_unique_tenant_lname"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tenant.slug})"


class StorageArea(models.Model):
    CODE_MAIN = "MAIN"

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="storage_areas")
    location = models.ForeignKey(
        BusinessLocation,
        on_delete=models.PROTECT,
        related_name="storage_areas",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=64)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["location_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["location", "code"], name="tenants_storage_unique_location_code"),
            models.UniqueConstraint(
                fields=["location"],
                condition=models.Q(is_default=True),
                name="tenants_storage_one_default_per_location",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} @ {self.location_id}"


class ApiApplication(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="api_applications")
    name = models.CharField(max_length=255)
    key_prefix = models.CharField(max_length=32)
    public_key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tenant.slug})"

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        super().clean()
        if not isinstance(self.scopes, list):
            raise ValidationError({"scopes": "Scopes must be a list."})
        invalid = set(self.scopes) - VALID_SCOPES
        if invalid:
            raise ValidationError({"scopes": f"Unknown scopes: {', '.join(sorted(invalid))}"})

    def set_token(self, raw_token: str | None = None) -> str:
        if raw_token is None:
            raw_token = generate_token(default_key_prefix())
        self.key_prefix = display_prefix(raw_token)
        self.public_key_hash = hash_token(raw_token)
        return raw_token

    @classmethod
    def create_with_token(
        cls,
        *,
        tenant: Tenant,
        name: str,
        scopes: list[str] | None = None,
        **kwargs,
    ) -> tuple["ApiApplication", str]:
        app = cls(
            tenant=tenant,
            name=name,
            scopes=scopes if scopes is not None else [],
            **kwargs,
        )
        raw_token = app.set_token()
        app.full_clean()
        app.save()
        return app, raw_token
