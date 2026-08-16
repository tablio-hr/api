from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.identity.authorization import (
    AuthorizationContext,
    authorize,
    current_episode_for,
    is_current_interval,
)
from apps.identity.login import normalize_primary_login
from apps.identity.models import MembershipEpisode, StaffAccessSession, StaffMembership, UserIdentity
from apps.identity.tokens import display_prefix, generate_staff_token, hash_token, verify_token
from apps.tenants.models import Tenant

DUMMY_PASSWORD_HASH = make_password("tablio-unused-dummy-password")
LOGIN_FAILED_DETAIL = "Invalid credentials."
LOGIN_FAILED_CODE = "invalid_credentials"


class LoginFailed(Exception):
    def __init__(self):
        super().__init__(LOGIN_FAILED_DETAIL)
        self.status = 401
        self.code = LOGIN_FAILED_CODE
        self.detail = LOGIN_FAILED_DETAIL


@dataclass(frozen=True)
class LoginResult:
    session: StaffAccessSession
    raw_token: str
    context: AuthorizationContext


def staff_session_ttl():
    hours = getattr(settings, "TABLIO_STAFF_SESSION_TTL_HOURS", 12)
    return timedelta(hours=hours)


def login_staff(
    *,
    primary_login: str,
    password: str,
    staff_membership_id: str | None = None,
) -> LoginResult:
    now = timezone.now()
    login = normalize_primary_login(primary_login)
    identity = UserIdentity.objects.filter(primary_login=login).first()
    if identity is None:
        check_password(password, DUMMY_PASSWORD_HASH)
        raise LoginFailed()

    if not identity.check_password(password):
        raise LoginFailed()
    if identity.status != UserIdentity.Status.ACTIVE:
        raise LoginFailed()

    membership = _selected_membership(identity, staff_membership_id)
    if membership is None:
        raise LoginFailed()
    if membership.tenant.status != Tenant.Status.ACTIVE:
        raise LoginFailed()

    episode = current_episode_for(membership)
    if (
        episode is None
        or episode.status != MembershipEpisode.Status.ACTIVE
        or not is_current_interval(now, episode.valid_from, episode.valid_until)
    ):
        raise LoginFailed()

    session, raw_token = issue_staff_session(membership=membership, episode=episode, now=now)
    context = authorize(session=session, now=now)
    return LoginResult(session=session, raw_token=raw_token, context=context)


def _selected_membership(identity: UserIdentity, staff_membership_id: str | None) -> StaffMembership | None:
    memberships = StaffMembership.objects.select_related("tenant").filter(user_identity=identity)
    if staff_membership_id:
        return memberships.filter(public_id=staff_membership_id).first()
    found = list(memberships[:2])
    if len(found) == 1:
        return found[0]
    return None


@transaction.atomic
def issue_staff_session(
    *,
    membership: StaffMembership,
    episode: MembershipEpisode,
    now=None,
) -> tuple[StaffAccessSession, str]:
    now = now or timezone.now()
    raw_token = generate_staff_token()
    session = StaffAccessSession.objects.create(
        tenant=membership.tenant,
        staff_membership=membership,
        membership_episode=episode,
        authorization_generation=membership.authorization_generation,
        token_prefix=display_prefix(raw_token),
        token_hash=hash_token(raw_token),
        expires_at=now + staff_session_ttl(),
    )
    return session, raw_token


def logout_staff(*, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = StaffAccessSession.objects.filter(token_hash=hash_token(raw_token)).first()
    if session is None or session.revoked_at is not None:
        return
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])


def session_from_token(raw_token: str) -> StaffAccessSession | None:
    session = (
        StaffAccessSession.objects.select_related(
            "tenant",
            "staff_membership",
            "staff_membership__user_identity",
            "membership_episode",
        )
        .filter(token_hash=hash_token(raw_token))
        .first()
    )
    if session is None or not verify_token(raw_token, session.token_hash):
        return None
    return session
