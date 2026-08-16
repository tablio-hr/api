from django.test import TestCase, override_settings

from apps.tenants.models import ApiApplication, Tenant


@override_settings(SECURE_SSL_REDIRECT=False)
class HostIsolationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo", slug="demo")
        self.app, self.token = ApiApplication.create_with_token(
            tenant=self.tenant,
            name="demo-app",
            scopes=["public:read"],
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_admin_on_api_hosts_is_404(self):
        for host in ("api.tablio.hr", "api-stage.tablio.hr"):
            response = self.client.get("/admin/", HTTP_HOST=host)
            self.assertEqual(response.status_code, 404, host)

    def test_api_on_admin_hosts_is_404(self):
        for host in ("admin.tablio.hr", "admin-stage.tablio.hr"):
            response = self.client.get("/api/v1/app/config", HTTP_HOST=host, **self.auth)
            self.assertEqual(response.status_code, 404, host)

    def test_early_access_on_admin_hosts_is_404(self):
        for host in ("admin.tablio.hr", "admin-stage.tablio.hr"):
            response = self.client.post(
                "/api/v1/early-access",
                data={"name": "Ana", "email": "ana@x.hr", "interest": "general"},
                content_type="application/json",
                HTTP_HOST=host,
            )
            self.assertEqual(response.status_code, 404, host)

    def test_api_on_api_host_is_not_isolation_404(self):
        response = self.client.get(
            "/api/v1/app/config",
            HTTP_HOST="api.tablio.hr",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_on_admin_host_is_not_isolation_404(self):
        response = self.client.get("/admin/", HTTP_HOST="admin.tablio.hr")
        self.assertNotEqual(response.status_code, 404)
        self.assertIn(response.status_code, (200, 302))

    def test_unknown_host_is_400(self):
        for path in ("/admin/", "/api/v1/app/config", "/health/", "/ready/"):
            response = self.client.get(path, HTTP_HOST="evil.example")
            self.assertEqual(response.status_code, 400, path)
