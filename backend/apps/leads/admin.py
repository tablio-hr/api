from django.contrib import admin

from apps.leads.models import EarlyAccessLead


@admin.register(EarlyAccessLead)
class EarlyAccessLeadAdmin(admin.ModelAdmin):
    list_display = ("email_normalized", "name", "interest", "created_at", "updated_at")
    search_fields = ("email_normalized", "name")
    list_filter = ("interest",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
