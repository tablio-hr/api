from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from apps.api.authentication import StaffSessionAuthentication
from apps.api.command_runner import run_staff_command
from apps.api.permissions import HasStaffSession
from apps.core.querysets import for_request_tenant
from apps.identity.models import ScopeType
from apps.identity.staff_commands import (
    activate_episode,
    add_location_assignment,
    add_role_assignment,
    create_staff_membership,
    end_episode,
    revoke_location_assignment,
    revoke_role_assignment,
    suspend_episode,
)
from apps.tenants.models import BusinessLocation


class StaffCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    primary_login = serializers.CharField(max_length=254)
    password = serializers.CharField()
    staff_number = serializers.CharField(max_length=32)
    invited = serializers.BooleanField(required=False, default=False)


class ScopeSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=ScopeType.choices)
    location_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        scope = attrs["scope_type"]
        location_id = attrs.get("location_id")
        if scope == ScopeType.TENANT and location_id:
            raise serializers.ValidationError("tenant scope must not include location_id.")
        if scope == ScopeType.LOCATION and not location_id:
            raise serializers.ValidationError("location scope requires location_id.")
        return attrs


class RoleAssignSerializer(ScopeSerializer):
    role = serializers.ChoiceField(choices=[("TENANT_ADMIN", "TENANT_ADMIN")])


def _scoped_location(request, data) -> BusinessLocation | None:
    location_id = data.get("location_id")
    if not location_id:
        return None
    try:
        return for_request_tenant(BusinessLocation.objects.all(), request).get(public_id=location_id)
    except BusinessLocation.DoesNotExist as exc:
        raise NotFound(detail="Not found.", code="not_found") from exc


class StaffMembershipCreateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def handler(authz):
            payload = create_staff_membership(
                authz,
                name=serializer.validated_data["name"],
                primary_login=serializer.validated_data["primary_login"],
                password=serializer.validated_data["password"],
                staff_number=serializer.validated_data["staff_number"],
                invited=serializer.validated_data.get("invited", False),
            )
            return 201, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.membership.create",
            handler=handler,
            resource_type="staff_membership",
        )


class EpisodeActivateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id):
        def handler(authz):
            payload = activate_episode(authz, membership_id=membership_id)
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.episode.activate",
            handler=handler,
            resource_type="staff_membership",
        )


class EpisodeSuspendView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id):
        def handler(authz):
            payload = suspend_episode(authz, membership_id=membership_id)
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.episode.suspend",
            handler=handler,
            resource_type="staff_membership",
        )


class EpisodeEndView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id):
        def handler(authz):
            payload = end_episode(authz, membership_id=membership_id)
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.episode.end",
            handler=handler,
            resource_type="staff_membership",
        )


class LocationAssignmentCreateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id):
        serializer = ScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = _scoped_location(request, serializer.validated_data)

        def handler(authz):
            payload = add_location_assignment(
                authz,
                membership_id=membership_id,
                scope_type=serializer.validated_data["scope_type"],
                location=location,
            )
            return 201, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.location_assignment.create",
            handler=handler,
            location=location,
            resource_type="location_assignment",
        )


class LocationAssignmentRevokeView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id, assignment_id):
        def handler(authz):
            payload = revoke_location_assignment(
                authz,
                membership_id=membership_id,
                assignment_id=assignment_id,
            )
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="staff.manage",
            action="staff.location_assignment.revoke",
            handler=handler,
            resource_type="location_assignment",
        )


class RoleAssignmentCreateView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id):
        serializer = RoleAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = _scoped_location(request, serializer.validated_data)

        def handler(authz):
            payload = add_role_assignment(
                authz,
                membership_id=membership_id,
                role_code=serializer.validated_data["role"],
                scope_type=serializer.validated_data["scope_type"],
                location=location,
            )
            return 201, payload, payload["id"]

        return run_staff_command(
            request,
            permission="role.assign",
            action="staff.role_assignment.create",
            handler=handler,
            location=location,
            resource_type="role_assignment",
        )


class RoleAssignmentRevokeView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def post(self, request, membership_id, assignment_id):
        def handler(authz):
            payload = revoke_role_assignment(
                authz,
                membership_id=membership_id,
                assignment_id=assignment_id,
            )
            return 200, payload, payload["id"]

        return run_staff_command(
            request,
            permission="role.assign",
            action="staff.role_assignment.revoke",
            handler=handler,
            resource_type="role_assignment",
        )
