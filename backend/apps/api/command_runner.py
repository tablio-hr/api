import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.api.models import CommandClaim
from apps.audit.services import write_success
from apps.identity.authorization import authorize
from apps.identity.errors import CommandDenied, ConflictDenied


def hash_idempotency_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_request_body(data) -> str:
    payload = data if isinstance(data, (dict, list)) else {}
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_staff_command(
    request,
    *,
    permission: str,
    action: str,
    handler,
    location=None,
    require_active_location: bool = False,
    resource_type: str = "",
):
    request._audit_action = action
    request._audit_permission = permission
    request._command_location = location
    request._command_require_active_location = require_active_location
    authz = authorize(
        session=request.staff_session,
        permission=permission,
        location=location,
        require_active_location=require_active_location,
    )
    request._audit_authz = authz
    raw_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()
    if not raw_key:
        raise ValidationError({"idempotency_key": "Idempotency-Key is required."})
    return _execute_idempotent(
        request,
        authz=authz,
        action=action,
        permission=permission,
        resource_type=resource_type,
        handler=handler,
        raw_key=raw_key,
    )


def _execute_idempotent(request, *, authz, action, permission, resource_type, handler, raw_key):
    now = timezone.now()
    lease = now + timedelta(seconds=getattr(settings, "TABLIO_IDEMPOTENCY_LEASE_SECONDS", 30))
    body_hash = hash_request_body(getattr(request, "data", {}))
    lookup = {
        "actor_type": "staff",
        "actor_id": str(authz.membership.public_id),
        "tenant": authz.tenant,
        "api_version": "v1",
        "method": request.method,
        "canonical_route": request.path,
        "idempotency_key_hash": hash_idempotency_key(raw_key),
    }
    replay = None
    denied = None
    result = None
    with transaction.atomic():
        claim, created = _lock_or_create_claim(lookup, body_hash=body_hash, lease=lease)
        if claim.status in (CommandClaim.Status.SUCCEEDED, CommandClaim.Status.FAILED_FINAL):
            if claim.request_body_hash != body_hash:
                raise ConflictDenied(code="idempotency_key_reuse", detail="Conflict.")
            replay = claim
        elif not created and claim.lease_expires_at > now:
            raise ConflictDenied(code="idempotency_in_progress", detail="Conflict.")
        else:
            result, denied = _run_handler(
                claim, authz, action, permission, resource_type, handler, body_hash
            )

    if denied is not None:
        raise denied
    if replay is not None:
        authorize(
            session=request.staff_session,
            permission=permission,
            location=getattr(request, "_command_location", None),
            require_active_location=bool(getattr(request, "_command_require_active_location", False)),
        )
        return Response(replay.response_body, status=replay.response_status)
    status, body = result
    return Response(body, status=status)


def _run_handler(claim, authz, action, permission, resource_type, handler, body_hash):
    try:
        status, body, resource_id = handler(authz)
    except CommandDenied as exc:
        claim.status = CommandClaim.Status.FAILED_FINAL
        claim.request_body_hash = body_hash
        claim.response_status = exc.status
        claim.response_body = exc.response_body
        claim.save(
            update_fields=["status", "request_body_hash", "response_status", "response_body", "updated_at"]
        )
        return None, exc
    write_success(
        authz=authz,
        action=action,
        permission=permission,
        resource_type=resource_type,
        resource_id=resource_id or "",
    )
    claim.status = CommandClaim.Status.SUCCEEDED
    claim.request_body_hash = body_hash
    claim.response_status = status
    claim.response_body = body
    claim.save(
        update_fields=["status", "request_body_hash", "response_status", "response_body", "updated_at"]
    )
    return (status, body), None


def _lock_or_create_claim(lookup: dict, *, body_hash: str, lease) -> tuple[CommandClaim, bool]:
    try:
        return CommandClaim.objects.select_for_update().get(**lookup), False
    except CommandClaim.DoesNotExist:
        try:
            return (
                CommandClaim.objects.create(
                    **lookup,
                    request_body_hash=body_hash,
                    status=CommandClaim.Status.IN_PROGRESS,
                    lease_expires_at=lease,
                ),
                True,
            )
        except IntegrityError:
            return CommandClaim.objects.select_for_update().get(**lookup), False
