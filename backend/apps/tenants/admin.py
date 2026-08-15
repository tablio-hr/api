from django.contrib import admin

from apps.tenants.models import ApiApplication, Tenant, TenantDomain, TenantMembership


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status")
    search_fields = ("name", "slug")


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_verified", "is_primary")


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant")


@admin.register(ApiApplication)
class ApiApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "key_prefix", "is_active", "expires_at")
    readonly_fields = ("key_prefix", "public_key_hash", "last_used_at")
