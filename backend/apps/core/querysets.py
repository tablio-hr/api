from django.core.exceptions import PermissionDenied


def for_request_tenant(qs, request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise PermissionDenied("Tenant is required.")
    return qs.filter(tenant=tenant)
