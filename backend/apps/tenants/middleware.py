from apps.tenants.models import Tenant, TenantDomain
from config.hosts import TABLIO_ADMIN_HOSTS, TABLIO_API_HOSTS, TABLIO_INTERNAL_HOSTS


def resolve_request_host(request) -> str:
    """Public Host only. X-Forwarded-Host is never trusted on the public edge."""
    return (request.META.get("HTTP_HOST") or "").split(":")[0].lower()


class TenantHostMiddleware:
    """Fail-closed tenant from verified active domain. No default tenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "tenant", None) is None:
            request.tenant = None
            request.tenant_domain = None
            host = resolve_request_host(request)
            if host and host not in TABLIO_ADMIN_HOSTS | TABLIO_API_HOSTS | TABLIO_INTERNAL_HOSTS:
                domain = (
                    TenantDomain.objects.select_related("tenant")
                    .filter(
                        domain=host,
                        is_verified=True,
                        tenant__status=Tenant.Status.ACTIVE,
                    )
                    .first()
                )
                if domain is not None:
                    request.tenant = domain.tenant
                    request.tenant_domain = domain
        return self.get_response(request)
