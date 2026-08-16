from django.db import models


class EarlyAccessLead(models.Model):
    """Platform-owned marketing lead. Not tenant data; no tenant_id and no IP."""

    class Interest(models.TextChoices):
        GENERAL = "general", "General"
        HANDHELD = "handheld", "Handheld"

    name = models.CharField(max_length=255)
    email_normalized = models.EmailField(max_length=254, unique=True)
    interest = models.CharField(max_length=16, choices=Interest.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email_normalized
