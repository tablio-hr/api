from django.db import models

from apps.tenants.models import Tenant


class AuditEvent(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        DENIED = "denied", "Denied"

    class ActorType(models.TextChoices):
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    actor_type = models.CharField(max_length=20, choices=ActorType.choices)
    actor_id = models.CharField(max_length=64, blank=True)
    user_identity_id = models.UUIDField(null=True, blank=True)
    staff_membership_id = models.UUIDField(null=True, blank=True)
    membership_episode_id = models.UUIDField(null=True, blank=True)
    authorization_generation = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=64)
    result = models.CharField(max_length=20, choices=Result.choices)
    permission = models.CharField(max_length=64, blank=True)
    resource_type = models.CharField(max_length=64, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.result} {self.action}"
