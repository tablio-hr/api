from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.authentication import StaffSessionAuthentication
from apps.api.credentials import authorization_bearer, reject_mixed_credentials
from apps.api.permissions import HasStaffSession
from apps.identity.access import login_staff, logout_staff
from apps.identity.authorization import authorize, context_payload


class StaffLoginSerializer(serializers.Serializer):
    primary_login = serializers.CharField()
    password = serializers.CharField()
    staff_membership_id = serializers.UUIDField(required=False, allow_null=True)


class StaffLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        reject_mixed_credentials(request)
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = login_staff(
            primary_login=serializer.validated_data["primary_login"],
            password=serializer.validated_data["password"],
            staff_membership_id=(
                str(serializer.validated_data["staff_membership_id"])
                if serializer.validated_data.get("staff_membership_id")
                else None
            ),
        )
        return Response(
            {
                "token": result.raw_token,
                "token_type": "Bearer",
                "expires_at": result.session.expires_at.isoformat(),
                "context": context_payload(result.context),
            }
        )


class StaffLogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        reject_mixed_credentials(request)
        logout_staff(raw_token=authorization_bearer(request))
        return Response(status=204)


class MeContextView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [HasStaffSession]

    def get(self, request):
        authz = authorize(session=request.staff_session)
        return Response(context_payload(authz))
