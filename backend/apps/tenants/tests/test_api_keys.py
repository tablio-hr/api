from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.api.views import AppConfigView
from apps.core.querysets import for_request_tenant
from apps.tenants.middleware import TenantHostMiddleware
from apps.tenants.models import ApiApplication, Tenant, TenantDomain
from apps.tenants.tokens import hash_token, verify_token


@override_settings(SECURE_SSL_REDIRECT=False)
class ApiKeyContractTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo", slug="demo")

    def _auth(self, token: str) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_HOST": "api.tablio.hr"}

    def test_valid_key_returns_config(self):
        _, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="ok", scopes=["public:read"]
        )
        response = self.client.get("/api/v1/app/config", **self._auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tenant"], "demo")

    def test_invalid_key_is_401(self):
        response = self.client.get("/api/v1/app/config", **self._auth("tablio_pk_test_nope"))
        self.assertEqual(response.status_code, 401)

    def test_inactive_key_is_401(self):
        app, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="off", scopes=["public:read"]
        )
        app.is_active = False
        app.save(update_fields=["is_active"])
        response = self.client.get("/api/v1/app/config", **self._auth(token))
        self.assertEqual(response.status_code, 401)

    def test_expired_key_is_401(self):
        app, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="old", scopes=["public:read"]
        )
        app.expires_at = timezone.now() - timedelta(minutes=1)
        app.save(update_fields=["expires_at"])
        response = self.client.get("/api/v1/app/config", **self._auth(token))
        self.assertEqual(response.status_code, 401)

    def test_token_not_stored_plaintext(self):
        app, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="hash-only", scopes=["public:read"]
        )
        app.refresh_from_db()
        field_names = {f.name for f in ApiApplication._meta.get_fields()}
        self.assertNotIn("token_encrypted", field_names)
        self.assertNotIn(token, {app.key_prefix, app.public_key_hash})
        self.assertTrue(verify_token(token, app.public_key_hash))
        self.assertEqual(app.public_key_hash, hash_token(token))

    def test_wrong_scope_is_403(self):
        _, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="public-only", scopes=["public:read"]
        )
        response = self.client.get("/api/v1/app/scope-probe", **self._auth(token))
        self.assertEqual(response.status_code, 403)

    def test_create_api_app_prints_token_once(self):
        stdout = StringIO()
        call_command("create_api_app", tenant="demo", name="cli", stdout=stdout)
        output = stdout.getvalue()
        app = ApiApplication.objects.get(name="cli")
        self.assertIn(app.key_prefix, output)
        raw_lines = [
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith("tablio_pk_")
        ]
        self.assertEqual(len(raw_lines), 1)
        self.assertTrue(verify_token(raw_lines[0], app.public_key_hash))
        self.assertNotEqual(raw_lines[0], app.public_key_hash)

    def test_suspended_tenant_key_is_generic_404(self):
        self.tenant.status = Tenant.Status.SUSPENDED
        self.tenant.save(update_fields=["status"])
        _, token = ApiApplication.create_with_token(
            tenant=self.tenant, name="sus", scopes=["public:read"]
        )
        captured = {}

        def _mark_view_ran(self, request):
            captured["ran"] = True
            captured["tenant"] = getattr(request, "tenant", "missing")
            captured["app"] = getattr(request, "api_application", "missing")
            raise AssertionError("view must not run")

        from rest_framework.exceptions import NotFound
        from rest_framework.test import APIRequestFactory

        from apps.api.authentication import AppKeyAuthentication

        factory = APIRequestFactory()
        auth_request = factory.get("/api/v1/app/config", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth_request.tenant = None
        auth_request.api_application = None
        with self.assertRaises(NotFound):
            AppKeyAuthentication().authenticate(auth_request)
        self.assertIsNone(auth_request.tenant)
        self.assertIsNone(auth_request.api_application)

        with patch.object(AppConfigView, "get", _mark_view_ran):
            response = self.client.get("/api/v1/app/config", **self._auth(token))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found.", "code": "not_found"})
        body = response.content.decode()
        self.assertNotIn("demo", body)
        self.assertNotIn("suspended", body.lower())
        self.assertNotIn(str(self.tenant.pk), body)
        self.assertFalse(captured.get("ran"))

    def test_host_does_not_select_tenant(self):
        TenantDomain.objects.create(
            tenant=self.tenant,
            domain="ghost.tablio.hr",
            is_verified=True,
        )
        factory = RequestFactory()
        request = factory.get("/", HTTP_HOST="ghost.tablio.hr")
        TenantHostMiddleware(lambda req: req)(request)
        self.assertIsNone(request.tenant)
        self.assertIsNone(request.api_application)

    def test_unknown_tenant_domain_does_not_default(self):
        TenantDomain.objects.create(
            tenant=self.tenant,
            domain="ghost.tablio.hr",
            is_verified=False,
        )
        response = self.client.get("/api/v1/app/config", HTTP_HOST="api.tablio.hr")
        self.assertEqual(response.status_code, 401)

    def test_for_request_tenant_requires_tenant(self):
        class Req:
            tenant = None

        with self.assertRaises(Exception):
            for_request_tenant(ApiApplication.objects.all(), Req())
