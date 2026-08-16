from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.leads.services import (
    SUCCESS_PAYLOAD,
    client_ip,
    normalize_email,
    notify_early_access,
    upsert_lead,
    verify_turnstile,
)
from config.hosts import TABLIO_MARKETING_ORIGINS


class EarlyAccessRateThrottle(AnonRateThrottle):
    scope = "early_access"

    def get_rate(self):
        return settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][self.scope]


class EarlyAccessSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        error_messages={
            "required": "Unesite ime.",
            "blank": "Unesite ime.",
            "null": "Unesite ime.",
        },
    )
    email = serializers.CharField(
        max_length=254,
        error_messages={
            "required": "Unesite valjanu e-mail adresu.",
            "blank": "Unesite valjanu e-mail adresu.",
            "null": "Unesite valjanu e-mail adresu.",
        },
    )
    interest = serializers.ChoiceField(
        choices=["general", "handheld"],
        error_messages={
            "required": "Odaberite interes.",
            "invalid_choice": "Odaberite interes.",
            "null": "Odaberite interes.",
        },
    )
    turnstile_token = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        normalized = normalize_email(value)
        try:
            EmailValidator(message="Unesite valjanu e-mail adresu.")(normalized)
        except DjangoValidationError as exc:
            raise serializers.ValidationError("Unesite valjanu e-mail adresu.") from exc
        return normalized


class EarlyAccessView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [EarlyAccessRateThrottle]

    def get_throttles(self):
        if self.request.method == "OPTIONS":
            return []
        return super().get_throttles()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        return _apply_marketing_cors(request, response)

    def options(self, request, *args, **kwargs):
        return Response(status=204)

    def post(self, request):
        if _honeypot_filled(request.data):
            return Response(SUCCESS_PAYLOAD)

        serializer = EarlyAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if settings.TURNSTILE_REQUIRED:
            token = serializer.validated_data.get("turnstile_token") or ""
            if not verify_turnstile(token, remote_ip=client_ip(request)):
                raise serializers.ValidationError(
                    {"turnstile_token": "Potvrda nije uspjela. Pokušajte ponovno."}
                )

        lead = upsert_lead(
            name=serializer.validated_data["name"],
            email_normalized=serializer.validated_data["email"],
            interest=serializer.validated_data["interest"],
        )
        notify_early_access(lead)
        return Response(SUCCESS_PAYLOAD)


def _honeypot_filled(data) -> bool:
    if not hasattr(data, "get"):
        return False
    value = data.get("website")
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _apply_marketing_cors(request, response):
    origin = request.headers.get("Origin") or request.META.get("HTTP_ORIGIN")
    if origin in TABLIO_MARKETING_ORIGINS:
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Access-Control-Max-Age"] = "86400"
        response["Vary"] = "Origin"
    return response
