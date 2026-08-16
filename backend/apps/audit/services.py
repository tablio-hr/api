import logging

from django.db import transaction

from apps.audit.models import AuditEvent
from apps.identity.authorization import AuthorizationContext

logger = logging.getLogger(__name__)


def write_success(
    *,
    authz: AuthorizationContext,
    action: str,
    permission: str = "",
    resource_type: str = "",
    resource_id: str = "",
) -> AuditEvent:
    return AuditEvent.objects.create(
        tenant=authz.tenant,
        actor_type=AuditEvent.ActorType.STAFF,
        actor_id=str(authz.membership.public_id),
        user_identity_id=authz.identity.public_id,
        staff_membership_id=authz.membership.public_id,
        membership_episode_id=authz.episode.public_id,
        authorization_generation=authz.membership.authorization_generation,
        action=action,
        result=AuditEvent.Result.SUCCESS,
        permission=permission,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else "",
    )


def write_denied(
    *,
    action: str,
    permission: str = "",
    resource_type: str = "",
    resource_id: str = "",
    authz: AuthorizationContext | None = None,
    tenant=None,
    actor_id: str = "",
) -> None:
    try:
        with transaction.atomic():
            AuditEvent.objects.create(
                tenant=authz.tenant if authz is not None else tenant,
                actor_type=AuditEvent.ActorType.STAFF,
                actor_id=str(authz.membership.public_id) if authz is not None else actor_id,
                user_identity_id=authz.identity.public_id if authz is not None else None,
                staff_membership_id=authz.membership.public_id if authz is not None else None,
                membership_episode_id=authz.episode.public_id if authz is not None else None,
                authorization_generation=(
                    authz.membership.authorization_generation if authz is not None else None
                ),
                action=action,
                result=AuditEvent.Result.DENIED,
                permission=permission,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else "",
            )
    except Exception:
        logger.exception("DENIED audit write failed")
