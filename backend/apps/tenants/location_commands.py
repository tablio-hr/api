from django.db import IntegrityError

from apps.identity.authorization import AuthorizationContext
from apps.identity.errors import ConflictDenied
from apps.tenants.models import BusinessLocation, StorageArea
from apps.tenants.services import create_business_location


def location_payload(location: BusinessLocation) -> dict:
    return {
        "id": str(location.public_id),
        "name": location.name,
        "timezone": location.timezone,
        "is_active": location.is_active,
    }


def create_location(authz: AuthorizationContext, *, name: str, timezone_name: str | None) -> dict:
    try:
        location = create_business_location(
            tenant=authz.tenant,
            name=name,
            timezone=timezone_name or authz.tenant.timezone,
        )
    except IntegrityError as exc:
        raise ConflictDenied(code="conflict", detail="Conflict.") from exc
    return location_payload(location)


def update_location(
    location: BusinessLocation,
    *,
    name: str | None = None,
    timezone_name: str | None = None,
    is_active: bool | None = None,
) -> dict:
    fields = ["updated_at"]
    if name is not None:
        location.name = name
        fields.append("name")
    if timezone_name is not None:
        location.timezone = timezone_name
        fields.append("timezone")
    if is_active is not None:
        location.is_active = is_active
        fields.append("is_active")
    try:
        location.save(update_fields=fields)
    except IntegrityError as exc:
        raise ConflictDenied(code="conflict", detail="Conflict.") from exc
    return location_payload(location)


def deactivate_location(location: BusinessLocation) -> dict:
    return update_location(location, is_active=False)


def location_has_main_storage(location: BusinessLocation) -> bool:
    return StorageArea.objects.filter(location=location, code=StorageArea.CODE_MAIN).exists()
