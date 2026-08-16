from django.db import transaction

from apps.tenants.models import BusinessLocation, StorageArea, Tenant


@transaction.atomic
def create_business_location(
    *,
    tenant: Tenant,
    name: str,
    timezone: str,
    is_active: bool = True,
) -> BusinessLocation:
    """Create a location and its MAIN storage in one transaction. Retry-safe on MAIN."""
    location = BusinessLocation.objects.create(
        tenant=tenant,
        name=name,
        timezone=timezone,
        is_active=is_active,
    )
    StorageArea.objects.get_or_create(
        location=location,
        code=StorageArea.CODE_MAIN,
        defaults={
            "tenant": tenant,
            "name": "Main",
            "is_default": True,
            "is_active": True,
        },
    )
    return location


def get_or_create_business_location(
    *,
    tenant: Tenant,
    name: str,
    timezone: str,
    is_active: bool = True,
) -> tuple[BusinessLocation, bool]:
    existing = BusinessLocation.objects.filter(tenant=tenant, name__iexact=name).first()
    if existing is not None:
        StorageArea.objects.get_or_create(
            location=existing,
            code=StorageArea.CODE_MAIN,
            defaults={
                "tenant": tenant,
                "name": "Main",
                "is_default": True,
                "is_active": True,
            },
        )
        return existing, False
    return create_business_location(
        tenant=tenant,
        name=name,
        timezone=timezone,
        is_active=is_active,
    ), True
