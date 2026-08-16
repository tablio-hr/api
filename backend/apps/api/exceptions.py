from rest_framework.exceptions import APIException, NotFound
from rest_framework.views import exception_handler as drf_exception_handler

from apps.api.credentials import MixedCredentials
from apps.audit.services import write_denied
from apps.identity.access import LoginFailed
from apps.identity.authorization import AuthorizeDenied
from apps.identity.errors import CommandDenied


def exception_handler(exc, context):
    original = exc
    if isinstance(exc, LoginFailed):
        exc = APIException(detail=exc.detail, code=exc.code)
        exc.status_code = 401
    elif isinstance(exc, (AuthorizeDenied, CommandDenied)):
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
    elif isinstance(exc, MixedCredentials):
        response.data = {"detail": str(exc.detail), "code": "mixed_credentials"}
    elif isinstance(response.data, dict) and "code" not in response.data:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        if isinstance(codes, str):
            response.data["code"] = codes
        elif isinstance(codes, dict) and isinstance(codes.get("detail"), str):
            response.data["code"] = codes["detail"]

    if response.status_code in (401, 403):
        _write_denied(context.get("request"), original)
    return response


def _write_denied(request, original) -> None:
    if request is None:
        return
    path = getattr(request, "path", "")
    if path.endswith("/auth/staff/login") or path.endswith("/auth/staff/logout"):
        return
    if isinstance(original, LoginFailed):
        return
    try:
        write_denied(
        action=getattr(request, "_audit_action", "") or path,
        permission=getattr(request, "_audit_permission", ""),
        authz=getattr(request, "_audit_authz", None),
        tenant=getattr(request, "tenant", None),
        actor_id=(
            str(request.staff_session.staff_membership.public_id)
            if getattr(request, "staff_session", None) is not None
            else ""
        ),
        )
    except Exception:
        return
