class TenantHostMiddleware:
    """Host never selects a tenant. request.tenant stays None until auth."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "tenant", None) is None:
            request.tenant = None
        if getattr(request, "api_application", None) is None:
            request.api_application = None
        if getattr(request, "staff_session", None) is None:
            request.staff_session = None
        return self.get_response(request)
