from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotFound

from apps.api.credentials import app_key_header, authorization_bearer, reject_mixed_credentials
from apps.identity.access import session_from_token
from apps.identity.tokens import is_staff_token
from apps.tenants.models import ApiApplication, Tenant
from apps.tenants.tokens import extract_token_from_request, hash_token, verify_token

LAST_USED_THROTTLE = timedelta(minutes=5)


class AppKeyAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        reject_mixed_credentials(request)
        raw_token = extract_token_from_request(request)
        if not raw_token:
            return None
        if is_staff_token(raw_token):
            return None

        token_hash = hash_token(raw_token)
        now = timezone.now()
        try:
            application = (
                ApiApplication.objects.select_related("tenant")
                .filter(public_key_hash=token_hash)
                .get()
            )
        except ApiApplication.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid API key.") from exc

        if not verify_token(raw_token, application.public_key_hash):
            raise AuthenticationFailed("Invalid API key.")
        if not application.is_active:
            raise AuthenticationFailed("Invalid API key.")
        if application.expires_at is not None and application.expires_at <= now:
            raise AuthenticationFailed("Invalid API key.")
        if application.tenant.status != Tenant.Status.ACTIVE:
            request.tenant = None
            request.api_application = None
            request.staff_session = None
            raise NotFound(detail="Not found.", code="not_found")

        request.tenant = application.tenant
        request.api_application = application
        request.staff_session = None
        self._touch_last_used(application)
        return (AnonymousUser(), application)

    def _touch_last_used(self, application: ApiApplication) -> None:
        now = timezone.now()
        if (
            application.last_used_at is not None
            and now - application.last_used_at < LAST_USED_THROTTLE
        ):
            return
        ApiApplication.objects.filter(pk=application.pk).update(last_used_at=now)
        application.last_used_at = now


class StaffSessionAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        reject_mixed_credentials(request)
        if app_key_header(request) and not authorization_bearer(request):
            return None
        raw_token = authorization_bearer(request)
        if not raw_token or not is_staff_token(raw_token):
            return None

        session = session_from_token(raw_token)
        if session is None:
            raise AuthenticationFailed(detail="Authentication required.", code="not_authenticated")
        now = timezone.now()
        if session.revoked_at is not None or session.expires_at <= now:
            raise AuthenticationFailed(detail="Authentication required.", code="not_authenticated")
        if session.tenant.status != Tenant.Status.ACTIVE:
            request.tenant = None
            request.staff_session = None
            request.api_application = None
            raise NotFound(detail="Not found.", code="not_found")

        request.tenant = session.tenant
        request.staff_session = session
        request.api_application = None
        return (None, session)
