from django.conf import settings
from django.http import HttpResponseNotFound
from django.middleware.security import SecurityMiddleware

from config.hosts import HEALTH_PATHS, TABLIO_ADMIN_HOSTS, TABLIO_API_HOSTS, TABLIO_INTERNAL_HOSTS


def request_host(request) -> str:
    return (request.META.get("HTTP_HOST") or "").split(":")[0].lower()


class TablioSecurityMiddleware(SecurityMiddleware):
    """SSL redirect with bypass only for /health/ and /ready/ on internal hosts."""

    def process_request(self, request):
        request.get_host()
        host = request_host(request)
        if request.path in HEALTH_PATHS and host in TABLIO_INTERNAL_HOSTS:
            previous = self.redirect
            self.redirect = False
            try:
                return super().process_request(request)
            finally:
                self.redirect = previous
        return super().process_request(request)


class HostIsolationMiddleware:
    """Allowed host + wrong surface → 404. Unknown host is 400 via ALLOWED_HOSTS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path in HEALTH_PATHS:
            return self.get_response(request)

        host = request_host(request)
        if path.startswith("/admin"):
            if host not in TABLIO_ADMIN_HOSTS:
                return HttpResponseNotFound()
        elif path.startswith("/api/v1"):
            if host not in TABLIO_API_HOSTS:
                return HttpResponseNotFound()
        return self.get_response(request)
