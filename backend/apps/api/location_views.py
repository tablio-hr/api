from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.authentication import StaffSessionAuthentication
from apps.api.command_runner import run_staff_command
from apps.api.permissions import HasStaffSession
from apps.core.querysets import for_request_tenant
from apps.identity.authorization import (
    AuthorizeDenied,
    authorize,
    has_permission_anywhere,
    visible_location_ids,
)
from apps.tenants.location_commands import create_location, deactivate_location, location_payload, update_location
from apps.tenants.models import BusinessLocation


class LocationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    timezone = serializers.CharField(max_length=64, required=False)


class LocationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    is_active = serializers.BooleanField(required=False)


def _location_or_404(request, public_id) -> BusinessLocation:
    try:
        return for_request_tenant(BusinessLocation.objects.all(), request).get(public_id=public_id)
    except BusinessLocation.DoesNotExist as exc:
        raise NotFound(detail="Not found.", code="not_found") from exc


class LocationListCreateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def get(self, request):
        request._audit_action = "location.list"
        request._audit_permission = "location.view"
        authz = authorize(session=request.staff_session)
        request._audit_authz = authz
        if not has_permission_anywhere(authz, "location.view"):
            raise AuthorizeDenied(403, "forbidden", "Forbidden.")
        qs = for_request_tenant(BusinessLocation.objects.all(), request).order_by("name")
        visible = visible_location_ids(authz)
        if visible is not None:
            qs = qs.filter(pk__in=visible)
        return Response({"locations": [location_payload(row) for row in qs]})

    def post(self, request):
        serializer = LocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def handler(authz):
            payload = create_location(
                authz,
                name=serializer.validated_data["name"],
                timezone_name=serializer.validated_data.get("timezone"),
            )
            return 201, payload, payload["id"]

        return run_staff_command(
            request,
            permission="location.manage",
            action="location.create",
            handler=handler,
            resource_type="location",
        )


class LocationDetailView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def get(self, request, public_id):
        request._audit_action = "location.get"
        request._audit_permission = "location.view"
        location = _location_or_404(request, public_id)
        authz = authorize(session=request.staff_session, permission="location.view", location=location)
        request._audit_authz = authz
        return Response(location_payload(location))

    def patch(self, request, public_id):
        location = _location_or_404(request, public_id)
        serializer = LocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def handler(authz):
            payload = update_location(
                location,
                name=serializer.validated_data.get("name"),
                timezone_name=serializer.validated_data.get("timezone"),
                is_active=serializer.validated_data.get("is_active"),
            )
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="location.manage",
            action="location.update",
            handler=handler,
            location=location,
            resource_type="location",
        )


class LocationDeactivateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, public_id):
        location = _location_or_404(request, public_id)

        def handler(authz):
            payload = deactivate_location(location)
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="location.manage",
            action="location.deactivate",
            handler=handler,
            location=location,
            resource_type="location",
        )
