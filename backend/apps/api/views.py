from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import HasApiApplication, HasRequiredScopes


class AppConfigView(APIView):
    permission_classes = [HasApiApplication, HasRequiredScopes]
    required_scopes = ["public:read"]

    def get(self, request):
        application = request.api_application
        return Response(
            {
                "tenant": request.tenant.slug,
                "scopes": list(application.scopes or []),
            }
        )


class ScopeProbeView(APIView):
    """Test-only style probe used by unit tests; also available for ops checks."""

    permission_classes = [HasApiApplication, HasRequiredScopes]
    required_scopes = ["admin:write"]

    def get(self, request):
        return Response({"ok": True})
