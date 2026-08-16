from rest_framework.exceptions import APIException


class MixedCredentials(APIException):
    status_code = 400
    default_detail = "Provide either a staff session or an API key, not both."
    default_code = "mixed_credentials"


def authorization_bearer(request) -> str | None:
    authorization = request.META.get("HTTP_AUTHORIZATION", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None
    return None


def app_key_header(request) -> str | None:
    key = request.META.get("HTTP_X_TABLIO_APP_KEY", "").strip()
    return key or None


def reject_mixed_credentials(request) -> None:
    if authorization_bearer(request) and app_key_header(request):
        raise MixedCredentials()
