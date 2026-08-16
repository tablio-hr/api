from django.contrib import admin

from apps.tenants.models import ApiApplication, BusinessLocation, StorageArea, Tenant, TenantDomain


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "public_id")
    search_fields = ("name", "slug")
    readonly_fields = ("public_id",)


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_verified", "is_primary")


@admin.register(BusinessLocation)
class BusinessLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "timezone", "is_active")
    search_fields = ("name",)
    readonly_fields = ("public_id",)


@admin.register(StorageArea)
class StorageAreaAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location", "tenant", "is_default", "is_active")
    readonly_fields = ("public_id",)


@admin.register(ApiApplication)
class ApiApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "key_prefix", "is_active", "expires_at")
    readonly_fields = ("key_prefix", "public_key_hash", "last_used_at")
