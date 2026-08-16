from django.contrib import admin

from apps.identity.models import (
    LocationAssignment,
    MembershipEpisode,
    Role,
    RoleAssignment,
    RoleVersion,
    StaffAccessSession,
    StaffMembership,
    UserIdentity,
)


@admin.register(UserIdentity)
class UserIdentityAdmin(admin.ModelAdmin):
    list_display = ("primary_login", "name", "status")
    search_fields = ("primary_login", "name")
    readonly_fields = ("public_id", "password")


@admin.register(StaffMembership)
class StaffMembershipAdmin(admin.ModelAdmin):
    list_display = ("staff_number", "tenant", "user_identity", "authorization_generation")
    readonly_fields = ("public_id",)


@admin.register(MembershipEpisode)
class MembershipEpisodeAdmin(admin.ModelAdmin):
    list_display = ("staff_membership", "version", "status", "valid_from", "valid_until")
    readonly_fields = ("public_id",)


@admin.register(LocationAssignment)
class LocationAssignmentAdmin(admin.ModelAdmin):
    list_display = ("staff_membership", "scope_type", "location", "status")
    readonly_fields = ("public_id",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system")


@admin.register(RoleVersion)
class RoleVersionAdmin(admin.ModelAdmin):
    list_display = ("role", "version")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("staff_membership", "role_version", "scope_type", "status")
    readonly_fields = ("public_id",)


@admin.register(StaffAccessSession)
class StaffAccessSessionAdmin(admin.ModelAdmin):
    list_display = ("token_prefix", "staff_membership", "expires_at", "revoked_at")
    readonly_fields = ("public_id", "token_prefix", "token_hash", "authorization_generation")
