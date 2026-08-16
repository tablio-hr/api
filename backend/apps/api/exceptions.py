from rest_framework.exceptions import APIException, NotFound
from rest_framework.views import exception_handler as drf_exception_handler

from apps.api.credentials import MixedCredentials
from apps.identity.access import LoginFailed
from apps.identity.authorization import AuthorizeDenied


def exception_handler(exc, context):
    if isinstance(exc, LoginFailed):
        exc = APIException(detail=exc.detail, code=exc.code)
        exc.status_code = 401
    elif isinstance(exc, AuthorizeDenied):
        if exc.status == 404:
            exc = NotFound(detail="Not found.", code="not_found")
        else:
            mapped = APIException(detail=exc.detail, code=exc.code)
            mapped.status_code = exc.status
            exc = mapped

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, NotFound):
        response.data = {"detail": "Not found.", "code": "not_found"}
        return response
    if isinstance(exc, MixedCredentials):
        response.data = {"detail": str(exc.detail), "code": "mixed_credentials"}
        return response
    if isinstance(response.data, dict) and "code" not in response.data:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        if isinstance(codes, str):
            response.data["code"] = codes
        elif isinstance(codes, dict) and isinstance(codes.get("detail"), str):
            response.data["code"] = codes["detail"]
    return response
