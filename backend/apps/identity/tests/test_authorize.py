from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.identity.authorization import AuthorizeDenied, authorize
from apps.identity.access import issue_staff_session
from apps.identity.models import (
    AssignmentStatus,
    LocationAssignment,
    MembershipEpisode,
    Role,
    RoleAssignment,
    RoleVersion,
    ScopeType,
    UserIdentity,
)
from apps.identity.services import bootstrap_tenant
from apps.tenants.models import Tenant
from apps.tenants.services import create_business_location


class AuthorizeTests(TestCase):
    def setUp(self):
        self.boot = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="secret-pass",
            location_names=["Front"],
        )
        self.now = timezone.now()
        self.session, _ = issue_staff_session(
            membership=self.boot.membership,
            episode=self.boot.episode,
            now=self.now,
        )
        self.location = self.boot.tenant.locations.get(name="Front")

    def test_active_session_authorizes_tenant_permission(self):
        authz = authorize(session=self.session, permission="location.view", now=self.now)
        self.assertEqual(authz.tenant.pk, self.boot.tenant.pk)
        self.assertEqual(authz.episode.pk, self.boot.episode.pk)
        self.assertIn("location.view", authz.permissions)
        self.assertIn("staff.manage", authz.permissions)

    def test_expired_session_is_401(self):
        self.session.expires_at = self.now - timedelta(seconds=1)
        self.session.save(update_fields=["expires_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 401)

    def test_revoked_session_is_401(self):
        self.session.revoked_at = self.now
        self.session.save(update_fields=["revoked_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 401)

    def test_generation_mismatch_is_401(self):
        self.boot.membership.authorization_generation = 1
        self.boot.membership.save(update_fields=["authorization_generation", "updated_at"])
        self.session.staff_membership.refresh_from_db()
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 401)

    def test_rehire_old_episode_session_is_401(self):
        self.boot.episode.status = MembershipEpisode.Status.ENDED
        self.boot.episode.valid_until = self.boot.episode.valid_from + timedelta(seconds=1)
        self.boot.episode.save(update_fields=["status", "valid_until", "updated_at"])
        bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="secret-pass",
            location_names=["Front"],
        )
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 401)

    def test_suspended_episode_is_403(self):
        self.boot.episode.status = MembershipEpisode.Status.SUSPENDED
        self.boot.episode.save(update_fields=["status", "updated_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 403)

    def test_ended_episode_without_rehire_is_403(self):
        self.boot.episode.status = MembershipEpisode.Status.ENDED
        self.boot.episode.valid_until = self.boot.episode.valid_from + timedelta(seconds=1)
        self.boot.episode.save(update_fields=["status", "valid_until", "updated_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 403)

    def test_invited_episode_is_403(self):
        self.boot.episode.status = MembershipEpisode.Status.INVITED
        self.boot.episode.save(update_fields=["status", "updated_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 403)

    def test_locked_identity_is_403(self):
        self.boot.identity.status = UserIdentity.Status.LOCKED
        self.boot.identity.save(update_fields=["status", "updated_at"])
        self.session.staff_membership.user_identity.refresh_from_db()
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 403)

    def test_suspended_tenant_is_404(self):
        self.boot.tenant.status = Tenant.Status.SUSPENDED
        self.boot.tenant.save(update_fields=["status"])
        self.session.tenant.refresh_from_db()
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, now=self.now)
        self.assertEqual(ctx.exception.status, 404)

    def test_episode_outside_interval_is_403(self):
        self.boot.episode.valid_until = self.boot.episode.valid_from + timedelta(seconds=1)
        self.boot.episode.save(update_fields=["valid_until", "updated_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(
                session=self.session,
                now=self.boot.episode.valid_until,
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_tenant_assignment_covers_location(self):
        authz = authorize(
            session=self.session,
            permission="location.view",
            location=self.location,
            now=self.now,
        )
        self.assertIn("location.view", authz.permissions)

    def test_location_command_without_covering_assignment_rejected(self):
        LocationAssignment.objects.filter(membership_episode=self.boot.episode).delete()
        other = create_business_location(
            tenant=self.boot.tenant,
            name="Back",
            timezone="Europe/Zagreb",
        )
        LocationAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=self.boot.membership,
            membership_episode=self.boot.episode,
            scope_type=ScopeType.LOCATION,
            location=other,
            status=AssignmentStatus.ACTIVE,
            valid_from=self.now,
        )
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(
                session=self.session,
                permission="location.view",
                location=self.location,
                now=self.now,
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_role_without_location_assignment_rejected(self):
        LocationAssignment.objects.filter(membership_episode=self.boot.episode).delete()
        RoleAssignment.objects.filter(membership_episode=self.boot.episode).delete()
        role = Role.objects.create(code="WAITER", name="Waiter", is_system=True)
        version = RoleVersion.objects.create(role=role, version=1, permissions=["location.view"])
        RoleAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=self.boot.membership,
            membership_episode=self.boot.episode,
            role_version=version,
            scope_type=ScopeType.LOCATION,
            location=self.location,
            status=AssignmentStatus.ACTIVE,
            valid_from=self.now,
        )
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(
                session=self.session,
                permission="location.view",
                location=self.location,
                now=self.now,
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_expired_assignment_rejected(self):
        LocationAssignment.objects.filter(membership_episode=self.boot.episode).update(
            valid_until=self.now,
        )
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(session=self.session, permission="location.view", now=self.now)
        self.assertEqual(ctx.exception.status, 403)

    def test_inactive_location_rejected_for_new_operation(self):
        self.location.is_active = False
        self.location.save(update_fields=["is_active", "updated_at"])
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(
                session=self.session,
                permission="location.manage",
                location=self.location,
                require_active_location=True,
                now=self.now,
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_foreign_location_rejected(self):
        other = Tenant.objects.create(name="Demo B", slug="demo-b")
        foreign = create_business_location(tenant=other, name="Away", timezone="Europe/Zagreb")
        with self.assertRaises(AuthorizeDenied) as ctx:
            authorize(
                session=self.session,
                permission="location.view",
                location=foreign,
                now=self.now,
            )
        self.assertEqual(ctx.exception.status, 403)
