from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.identity.models import MembershipEpisode, StaffAccessSession, UserIdentity
from apps.identity.services import bootstrap_tenant
from apps.identity.tokens import hash_token, verify_token
from apps.tenants.models import ApiApplication, Tenant


LOGIN_DENIED = {"detail": "Invalid credentials.", "code": "invalid_credentials"}


@override_settings(SECURE_SSL_REDIRECT=False)
class StaffAuthHttpTests(TestCase):
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

    def _login(self, **body):
        payload = {"primary_login": "admin@demo.hr", "password": "secret-pass"}
        payload.update(body)
        return self.client.post(
            "/api/v1/auth/staff/login",
            data=payload,
            content_type="application/json",
            **self.host,
        )

    def test_login_returns_token_once_and_stores_hash(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        token = body["token"]
        self.assertTrue(token.startswith("tablio_st_"))
        self.assertEqual(body["token_type"], "Bearer")
        self.assertIn("expires_at", body)
        session = StaffAccessSession.objects.get()
        self.assertNotEqual(token, session.token_hash)
        self.assertTrue(verify_token(token, session.token_hash))
        self.assertEqual(session.token_hash, hash_token(token))
        self.assertEqual(body["context"]["tenant"]["slug"], "demo-a")
        self.assertEqual(body["context"]["identity"]["primary_login"], "admin@demo.hr")
        self.assertIn("location.view", body["context"]["permissions"])

    def test_login_is_case_insensitive_and_trimmed(self):
        response = self._login(primary_login="  Admin@Demo.HR  ")
        self.assertEqual(response.status_code, 200)

    def test_login_failures_share_the_same_body(self):
        cases = [
            {"primary_login": "nobody@demo.hr", "password": "secret-pass"},
            {"primary_login": "admin@demo.hr", "password": "wrong-pass"},
        ]
        self.boot.identity.status = UserIdentity.Status.DISABLED
        self.boot.identity.save(update_fields=["status", "updated_at"])
        cases.append({"primary_login": "admin@demo.hr", "password": "secret-pass"})
        bodies = []
        for payload in cases:
            response = self._login(**payload)
            self.assertEqual(response.status_code, 401, payload)
            self.assertEqual(response.json(), LOGIN_DENIED)
            bodies.append(response.json())
        self.assertEqual(bodies[0], bodies[1])
        self.assertEqual(bodies[1], bodies[2])

    def test_locked_and_invited_and_foreign_membership_are_same_401(self):
        self.boot.identity.status = UserIdentity.Status.LOCKED
        self.boot.identity.save(update_fields=["status", "updated_at"])
        locked = self._login()
        self.boot.identity.status = UserIdentity.Status.ACTIVE
        self.boot.identity.save(update_fields=["status", "updated_at"])

        self.boot.episode.status = MembershipEpisode.Status.INVITED
        self.boot.episode.save(update_fields=["status", "updated_at"])
        invited = self._login()
        self.boot.episode.status = MembershipEpisode.Status.ACTIVE
        self.boot.episode.save(update_fields=["status", "updated_at"])

        other = bootstrap_tenant(
            slug="demo-b",
            name="Demo B",
            timezone_name="Europe/Zagreb",
            admin_login="other@demo.hr",
            admin_name="Other",
            admin_password="other-pass",
            location_names=["Hall"],
        )
        foreign = self._login(staff_membership_id=str(other.membership.public_id))
        for response in (locked, invited, foreign):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), LOGIN_DENIED)

    def test_two_memberships_require_selection(self):
        bootstrap_tenant(
            slug="demo-b",
            name="Demo B",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="secret-pass",
            location_names=["Hall"],
        )
        missing = self._login()
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json(), LOGIN_DENIED)
        selected = self._login(staff_membership_id=str(self.boot.membership.public_id))
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["context"]["tenant"]["slug"], "demo-a")

    def test_body_tenant_id_and_staff_id_do_not_change_actor(self):
        other = bootstrap_tenant(
            slug="demo-b",
            name="Demo B",
            timezone_name="Europe/Zagreb",
            admin_login="other@demo.hr",
            admin_name="Other",
            admin_password="other-pass",
            location_names=["Hall"],
        )
        response = self._login(
            tenant_id=str(other.tenant.public_id),
            staff_id=str(other.identity.public_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["context"]["tenant"]["slug"], "demo-a")
        self.assertEqual(response.json()["context"]["identity"]["primary_login"], "admin@demo.hr")

    def test_me_context_matches_login_and_ignores_query_tenant(self):
        login = self._login().json()
        token = login["token"]
        response = self.client.get(
            "/api/v1/me/context",
            {"tenant_id": "should-be-ignored"},
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), login["context"])

    def test_expired_session_is_401(self):
        token = self._login().json()["token"]
        session = StaffAccessSession.objects.get()
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["expires_at"])
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_generation_mismatch_is_401(self):
        token = self._login().json()["token"]
        self.boot.membership.authorization_generation = 3
        self.boot.membership.save(update_fields=["authorization_generation", "updated_at"])
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_logout_is_idempotent_204(self):
        token = self._login().json()["token"]
        first = self.client.post(
            "/api/v1/auth/staff/logout",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        second = self.client.post(
            "/api/v1/auth/staff/logout",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        unknown = self.client.post(
            "/api/v1/auth/staff/logout",
            HTTP_AUTHORIZATION="Bearer tablio_st_unknown-token-value",
            **self.host,
        )
        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 204)
        self.assertEqual(unknown.status_code, 204)
        denied = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(denied.status_code, 401)

    def test_staff_token_fails_on_api_key_path(self):
        token = self._login().json()["token"]
        response = self.client.get(
            "/api/v1/app/config",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 401)

    def test_api_key_fails_on_staff_path(self):
        _, key = ApiApplication.create_with_token(
            tenant=self.boot.tenant,
            name="machine",
            scopes=["public:read"],
        )
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {key}",
            **self.host,
        )
        self.assertEqual(response.status_code, 401)

    def test_both_headers_are_400(self):
        token = self._login().json()["token"]
        _, key = ApiApplication.create_with_token(
            tenant=self.boot.tenant,
            name="machine",
            scopes=["public:read"],
        )
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TABLIO_APP_KEY=key,
            **self.host,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "mixed_credentials")
        machine = self.client.get(
            "/api/v1/app/config",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TABLIO_APP_KEY=key,
            **self.host,
        )
        self.assertEqual(machine.status_code, 400)

    def test_suspended_tenant_is_generic_404(self):
        token = self._login().json()["token"]
        self.boot.tenant.status = Tenant.Status.SUSPENDED
        self.boot.tenant.save(update_fields=["status"])
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found.", "code": "not_found"})
        body = response.content.decode()
        self.assertNotIn("demo-a", body)
        self.assertNotIn("suspended", body.lower())

    def test_token_not_in_error_payload(self):
        token = self._login().json()["token"]
        StaffAccessSession.objects.update(revoked_at=timezone.now())
        response = self.client.get(
            "/api/v1/me/context",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **self.host,
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(token, response.content.decode())
