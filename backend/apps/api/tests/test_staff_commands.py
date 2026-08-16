import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from datetime import timedelta

from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import write_success
from apps.identity.access import issue_staff_session
from apps.identity.authorization import authorize
from apps.identity.models import (
    AssignmentStatus,
    LocationAssignment,
    MembershipEpisode,
    Role,
    RoleAssignment,
    RoleVersion,
    ScopeType,
    StaffMembership,
    UserIdentity,
)
from apps.identity.services import bootstrap_tenant
from apps.tenants.models import ApiApplication, StorageArea, Tenant
from apps.tenants.services import create_business_location


@override_settings(SECURE_SSL_REDIRECT=False)
class StaffCommandTests(TestCase):
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
        self.host = {"HTTP_HOST": "api.tablio.hr"}
        self.token = self._login("admin@demo.hr", "secret-pass")
        self.front_id = str(self.boot.tenant.locations.get(name="Front").public_id)
        self.keys = 0

    def _login(self, primary_login, password, staff_membership_id=None):
        body = {"primary_login": primary_login, "password": password}
        if staff_membership_id:
            body["staff_membership_id"] = staff_membership_id
        response = self.client.post(
            "/api/v1/auth/staff/login",
            data=body,
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["token"]

    def _key(self) -> str:
        self.keys += 1
        return f"key-{self.keys}-{uuid.uuid4()}"

    def _auth(self, token, key=None):
        headers = {**self.host, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        if key is not None:
            headers["HTTP_IDEMPOTENCY_KEY"] = key
        return headers

    def _post(self, path, token, data=None, key=None):
        return self.client.post(
            path,
            data=data or {},
            content_type="application/json",
            **self._auth(token, key if key is not None else self._key()),
        )

    def _create_staff(self, token, **overrides):
        body = {
            "name": "Bea",
            "primary_login": "bea@demo.hr",
            "password": "bea-pass",
            "staff_number": "2",
        }
        body.update(overrides)
        response = self._post("/api/v1/staff/memberships", token, body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def _grant_tenant_admin(self, token, membership_id):
        loc = self._post(
            f"/api/v1/staff/memberships/{membership_id}/location-assignments",
            token,
            {"scope_type": "tenant"},
        )
        self.assertEqual(loc.status_code, 201, loc.content)
        role = self._post(
            f"/api/v1/staff/memberships/{membership_id}/role-assignments",
            token,
            {"role": "TENANT_ADMIN", "scope_type": "tenant"},
        )
        self.assertEqual(role.status_code, 201, role.content)
        return loc.json(), role.json()

    def test_same_person_two_tenants_session_stays_on_a(self):
        other = bootstrap_tenant(
            slug="demo-b",
            name="Demo B",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="secret-pass",
            location_names=["Hall"],
        )
        hall_id = str(other.tenant.locations.get(name="Hall").public_id)
        response = self.client.get(
            f"/api/v1/locations/{hall_id}",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 404)
        created = self._post("/api/v1/locations", self.token, {"name": "Side", "tenant_id": str(other.tenant.public_id)})
        self.assertEqual(created.status_code, 201)
        self.assertTrue(
            self.boot.tenant.locations.filter(name="Side").exists()
        )
        self.assertFalse(other.tenant.locations.filter(name="Side").exists())

    def test_second_membership_same_identity_conflict(self):
        response = self._post(
            "/api/v1/staff/memberships",
            self.token,
            {
                "name": "Admin",
                "primary_login": "admin@demo.hr",
                "password": "secret-pass",
                "staff_number": "9",
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_invited_and_suspended_and_ended_are_403_and_rehire_inherits_nothing(self):
        staff = self._create_staff(self.token)
        self._grant_tenant_admin(self.token, staff["id"])
        bea_token = self._login("bea@demo.hr", "bea-pass")
        membership = StaffMembership.objects.get(public_id=staff["id"])
        episode = membership.episodes.get(status=MembershipEpisode.Status.ACTIVE)
        LocationAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=membership,
            membership_episode=episode,
            scope_type=ScopeType.LOCATION,
            location=self.boot.tenant.locations.get(name="Front"),
            status=AssignmentStatus.ACTIVE,
            valid_from=timezone.now(),
        )

        episode.status = MembershipEpisode.Status.INVITED
        episode.save(update_fields=["status", "updated_at"])
        invited = self.client.get("/api/v1/locations", **self._auth(bea_token))
        self.assertEqual(invited.status_code, 403)

        episode.status = MembershipEpisode.Status.ACTIVE
        episode.save(update_fields=["status", "updated_at"])
        suspend = self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:suspend", self.token)
        self.assertEqual(suspend.status_code, 200)
        suspended = self.client.get("/api/v1/locations", **self._auth(bea_token))
        self.assertEqual(suspended.status_code, 401)

        activate = self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:activate", self.token)
        self.assertEqual(activate.status_code, 200)
        ended = self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:end", self.token)
        self.assertEqual(ended.status_code, 200)
        rehire = self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:activate", self.token)
        self.assertEqual(rehire.status_code, 200)
        self.assertEqual(rehire.json()["episode"]["version"], 2)
        self.assertEqual(
            LocationAssignment.objects.filter(membership_episode__public_id=rehire.json()["episode"]["id"]).count(),
            0,
        )
        self.assertEqual(
            RoleAssignment.objects.filter(membership_episode__public_id=rehire.json()["episode"]["id"]).count(),
            0,
        )
        old_session = self.client.get("/api/v1/me/context", **self._auth(bea_token))
        self.assertEqual(old_session.status_code, 401)

    def test_body_staff_id_does_not_change_actor(self):
        staff = self._create_staff(self.token)
        response = self._post(
            "/api/v1/locations",
            self.token,
            {"name": "Garden", "staff_id": staff["id"], "tenant_id": "ignored"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            AuditEvent.objects.get(action="location.create", result=AuditEvent.Result.SUCCESS).actor_id,
            str(self.boot.membership.public_id),
        )

    def test_me_context_matches_command_tenant(self):
        context = self.client.get("/api/v1/me/context", **self._auth(self.token)).json()
        created = self._post("/api/v1/locations", self.token, {"name": "Patio"})
        self.assertEqual(created.status_code, 201)
        listed = self.client.get("/api/v1/locations", **self._auth(self.token)).json()
        self.assertEqual(context["tenant"]["slug"], "demo-a")
        self.assertTrue(any(row["name"] == "Patio" for row in listed["locations"]))
        self.assertIn("location.manage", context["permissions"])

    def test_tenant_assignment_covers_new_location(self):
        created = self._post("/api/v1/locations", self.token, {"name": "New Hall"})
        self.assertEqual(created.status_code, 201)
        location_id = created.json()["id"]
        detail = self.client.get(f"/api/v1/locations/{location_id}", **self._auth(self.token))
        self.assertEqual(detail.status_code, 200)
        patched = self.client.patch(
            f"/api/v1/locations/{location_id}",
            data={"name": "New Hall 2"},
            content_type="application/json",
            **self._auth(self.token, self._key()),
        )
        self.assertEqual(patched.status_code, 200)
        self.assertTrue(
            StorageArea.objects.filter(
                location__public_id=location_id,
                code=StorageArea.CODE_MAIN,
            ).exists()
        )

    def test_location_scope_without_covering_assignment_rejected(self):
        staff = self._create_staff(self.token)
        membership = StaffMembership.objects.get(public_id=staff["id"])
        episode = membership.episodes.get()
        other = create_business_location(tenant=self.boot.tenant, name="Back", timezone="Europe/Zagreb")
        LocationAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=membership,
            membership_episode=episode,
            scope_type=ScopeType.LOCATION,
            location=other,
            status=AssignmentStatus.ACTIVE,
            valid_from=timezone.now(),
        )
        RoleAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=membership,
            membership_episode=episode,
            role_version=RoleVersion.objects.get(role__code=Role.TENANT_ADMIN),
            scope_type=ScopeType.TENANT,
            status=AssignmentStatus.ACTIVE,
            valid_from=timezone.now(),
        )
        bea_token = self._login("bea@demo.hr", "bea-pass")
        response = self.client.get(f"/api/v1/locations/{self.front_id}", **self._auth(bea_token))
        self.assertEqual(response.status_code, 403)

    def test_role_without_location_assignment_rejected(self):
        staff = self._create_staff(self.token)
        membership = StaffMembership.objects.get(public_id=staff["id"])
        episode = membership.episodes.get()
        RoleAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=membership,
            membership_episode=episode,
            role_version=RoleVersion.objects.get(role__code=Role.TENANT_ADMIN),
            scope_type=ScopeType.LOCATION,
            location=self.boot.tenant.locations.get(name="Front"),
            status=AssignmentStatus.ACTIVE,
            valid_from=timezone.now(),
        )
        bea_token = self._login("bea@demo.hr", "bea-pass")
        response = self.client.get(f"/api/v1/locations/{self.front_id}", **self._auth(bea_token))
        self.assertEqual(response.status_code, 403)

    def test_self_assignment_of_stronger_role_rejected(self):
        staff = self._create_staff(self.token)
        self._grant_tenant_admin(self.token, staff["id"])
        membership = StaffMembership.objects.get(public_id=staff["id"])
        RoleAssignment.objects.filter(staff_membership=membership).delete()
        weak = Role.objects.create(code="ASSIGNER", name="Assigner", is_system=True)
        version = RoleVersion.objects.create(role=weak, version=1, permissions=["role.assign", "location.view"])
        RoleAssignment.objects.create(
            tenant=self.boot.tenant,
            staff_membership=membership,
            membership_episode=membership.episodes.get(status=MembershipEpisode.Status.ACTIVE),
            role_version=version,
            scope_type=ScopeType.TENANT,
            status=AssignmentStatus.ACTIVE,
            valid_from=timezone.now(),
        )
        bea_token = self._login("bea@demo.hr", "bea-pass")
        response = self._post(
            f"/api/v1/staff/memberships/{staff['id']}/role-assignments",
            bea_token,
            {"role": "TENANT_ADMIN", "scope_type": "tenant"},
        )
        self.assertEqual(response.status_code, 403)

    def test_last_admin_cannot_be_removed(self):
        response = self._post(
            f"/api/v1/staff/memberships/{self.boot.membership.public_id}/episodes:end",
            self.token,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "last_admin")
        self.boot.episode.refresh_from_db()
        self.assertEqual(self.boot.episode.status, MembershipEpisode.Status.ACTIVE)

    def test_second_admin_can_be_removed_then_last_is_protected(self):
        staff = self._create_staff(self.token)
        self._grant_tenant_admin(self.token, staff["id"])
        removed = self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:suspend", self.token)
        self.assertEqual(removed.status_code, 200)
        blocked = self._post(
            f"/api/v1/staff/memberships/{self.boot.membership.public_id}/episodes:suspend",
            self.token,
        )
        self.assertEqual(blocked.status_code, 403)

    def test_assignment_change_invalidates_target_session(self):
        staff = self._create_staff(self.token)
        self._grant_tenant_admin(self.token, staff["id"])
        bea_token = self._login("bea@demo.hr", "bea-pass")
        self.assertEqual(self.client.get("/api/v1/me/context", **self._auth(bea_token)).status_code, 200)
        assignment = LocationAssignment.objects.get(
            staff_membership__public_id=staff["id"],
            scope_type=ScopeType.TENANT,
        )
        revoked = self._post(
            f"/api/v1/staff/memberships/{staff['id']}/location-assignments/{assignment.public_id}:revoke",
            self.token,
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/me/context", **self._auth(bea_token)).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/me/context", **self._auth(self.token)).status_code, 200)

    def test_idempotency_retry_and_different_body(self):
        key = self._key()
        first = self._post("/api/v1/locations", self.token, {"name": "Retry Hall"}, key=key)
        second = self._post("/api/v1/locations", self.token, {"name": "Retry Hall"}, key=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.boot.tenant.locations.filter(name="Retry Hall").count(), 1)
        reuse = self._post("/api/v1/locations", self.token, {"name": "Other Hall"}, key=key)
        self.assertEqual(reuse.status_code, 409)
        self.assertEqual(reuse.json()["code"], "idempotency_key_reuse")

    def test_idempotency_replay_after_suspend_is_denied(self):
        staff = self._create_staff(self.token)
        self._grant_tenant_admin(self.token, staff["id"])
        bea_token = self._login("bea@demo.hr", "bea-pass")
        key = self._key()
        created = self._post("/api/v1/locations", bea_token, {"name": "Bea Hall"}, key=key)
        self.assertEqual(created.status_code, 201)
        self._post(f"/api/v1/staff/memberships/{staff['id']}/episodes:suspend", self.token)
        replay = self._post("/api/v1/locations", bea_token, {"name": "Bea Hall"}, key=key)
        self.assertIn(replay.status_code, (401, 403))
        self.assertEqual(self.boot.tenant.locations.filter(name="Bea Hall").count(), 1)

    def test_success_audit_rolls_back_with_command(self):
        session, _ = issue_staff_session(membership=self.boot.membership, episode=self.boot.episode)
        authz = authorize(session=session)
        try:
            with transaction.atomic():
                write_success(authz=authz, action="location.create", permission="location.manage")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        self.assertFalse(AuditEvent.objects.filter(action="location.create").exists())

    def test_denied_write_failure_does_not_become_500(self):
        with patch("apps.api.exceptions.write_denied", side_effect=RuntimeError("audit down")):
            response = self._post(
                f"/api/v1/staff/memberships/{self.boot.membership.public_id}/episodes:end",
                self.token,
            )
        self.assertEqual(response.status_code, 403)
        self.boot.episode.refresh_from_db()
        self.assertEqual(self.boot.episode.status, MembershipEpisode.Status.ACTIVE)

    def test_deactivated_location_is_readable(self):
        deactivated = self._post(f"/api/v1/locations/{self.front_id}:deactivate", self.token)
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.json()["is_active"])
        detail = self.client.get(f"/api/v1/locations/{self.front_id}", **self._auth(self.token))
        self.assertEqual(detail.status_code, 200)
        listed = self.client.get("/api/v1/locations", **self._auth(self.token)).json()
        self.assertTrue(any(row["id"] == self.front_id and not row["is_active"] for row in listed["locations"]))

    def test_api_key_cannot_manage_locations(self):
        _, key = ApiApplication.create_with_token(
            tenant=self.boot.tenant,
            name="machine",
            scopes=["public:read", "admin:write"],
        )
        response = self.client.post(
            "/api/v1/locations",
            data={"name": "Machine"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {key}",
            HTTP_IDEMPOTENCY_KEY=self._key(),
            **self.host,
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_idempotency_key_is_400(self):
        response = self.client.post(
            "/api/v1/locations",
            data={"name": "No Key"},
            content_type="application/json",
            **self._auth(self.token),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.boot.tenant.locations.filter(name="No Key").exists())


@skipUnless(connection.vendor == "postgresql", "Parallel command tests need PostgreSQL row locks.")
@override_settings(SECURE_SSL_REDIRECT=False)
class ParallelStaffCommandTests(TransactionTestCase):
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
        self.host = {"HTTP_HOST": "api.tablio.hr"}

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def _login(self):
        response = self.client.post(
            "/api/v1/auth/staff/login",
            data={"primary_login": "admin@demo.hr", "password": "secret-pass"},
            content_type="application/json",
            **self.host,
        )
        return response.json()["token"]

    def test_parallel_last_admin_removals_only_one_succeeds(self):
        token = self._login()
        create = self.client.post(
            "/api/v1/staff/memberships",
            data={
                "name": "Bea",
                "primary_login": "bea@demo.hr",
                "password": "bea-pass",
                "staff_number": "2",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **self.host,
        )
        membership_id = create.json()["id"]
        self.client.post(
            f"/api/v1/staff/memberships/{membership_id}/location-assignments",
            data={"scope_type": "tenant"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **self.host,
        )
        self.client.post(
            f"/api/v1/staff/memberships/{membership_id}/role-assignments",
            data={"role": "TENANT_ADMIN", "scope_type": "tenant"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **self.host,
        )
        bea = self.client.post(
            "/api/v1/auth/staff/login",
            data={"primary_login": "bea@demo.hr", "password": "bea-pass"},
            content_type="application/json",
            **self.host,
        ).json()["token"]

        def _end(actor_token, target_id, key):
            try:
                client = self.client_class()
                return client.post(
                    f"/api/v1/staff/memberships/{target_id}/episodes:end",
                    data={},
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {actor_token}",
                    HTTP_IDEMPOTENCY_KEY=key,
                    HTTP_HOST="api.tablio.hr",
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_end, token, membership_id, str(uuid.uuid4()))
            second = pool.submit(_end, bea, str(self.boot.membership.public_id), str(uuid.uuid4()))
            codes = sorted([first.result(), second.result()])
        self.assertEqual(codes, [200, 403])
        ended = MembershipEpisode.objects.filter(
            staff_membership__tenant=self.boot.tenant,
            status=MembershipEpisode.Status.ENDED,
        ).count()
        self.assertEqual(ended, 1)

    def test_parallel_activate_does_not_create_two_current_episodes(self):
        token = self._login()
        created = self.client.post(
            "/api/v1/staff/memberships",
            data={
                "name": "Bea",
                "primary_login": "bea@demo.hr",
                "password": "bea-pass",
                "staff_number": "2",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **self.host,
        )
        membership_id = created.json()["id"]
        ended = self.client.post(
            f"/api/v1/staff/memberships/{membership_id}/episodes:end",
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **self.host,
        )
        self.assertEqual(ended.status_code, 200)

        def _activate(key):
            try:
                client = self.client_class()
                return client.post(
                    f"/api/v1/staff/memberships/{membership_id}/episodes:activate",
                    data={},
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                    HTTP_IDEMPOTENCY_KEY=key,
                    HTTP_HOST="api.tablio.hr",
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(_activate, str(uuid.uuid4()))
            second = pool.submit(_activate, str(uuid.uuid4()))
            statuses = {first.result().status_code, second.result().status_code}
        self.assertTrue(statuses <= {200})
        self.assertEqual(
            MembershipEpisode.objects.filter(
                staff_membership__public_id=membership_id,
                status__in=MembershipEpisode.CURRENT_STATUSES,
            ).count(),
            1,
        )

    def test_parallel_idempotency_one_side_effect(self):
        token = self._login()
        key = str(uuid.uuid4())

        def _create():
            try:
                client = self.client_class()
                return client.post(
                    "/api/v1/locations",
                    data={"name": "Parallel Hall"},
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                    HTTP_IDEMPOTENCY_KEY=key,
                    HTTP_HOST="api.tablio.hr",
                ).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted([pool.submit(_create).result(), pool.submit(_create).result()])
        self.assertEqual(self.boot.tenant.locations.filter(name="Parallel Hall").count(), 1)
        self.assertIn(201, codes)
        self.assertTrue(set(codes) <= {201, 409})
