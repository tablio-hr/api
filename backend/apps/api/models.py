from django.db import models

from apps.tenants.models import Tenant


class CommandClaim(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED_FINAL = "failed_final", "Failed final"

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="command_claims")
    actor_type = models.CharField(max_length=20)
    actor_id = models.CharField(max_length=64)
    api_version = models.CharField(max_length=16)
    method = models.CharField(max_length=10)
    canonical_route = models.CharField(max_length=255)
    idempotency_key_hash = models.CharField(max_length=64)
    request_body_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices)
    lease_expires_at = models.DateTimeField()
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "actor_type",
                    "actor_id",
                    "tenant",
                    "api_version",
                    "method",
                    "canonical_route",
                    "idempotency_key_hash",
                ],
                name="api_commandclaim_unique_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.canonical_route} ({self.status})"
