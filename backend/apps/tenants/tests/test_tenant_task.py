from django.test import TestCase

from apps.core.tasks import ping
from apps.tenants.models import Tenant
from apps.tenants.tasks import TenantTask, probe_tenant


class TenantTaskTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo", slug="demo")

    def test_ping_is_not_tenant_task(self):
        self.assertFalse(issubclass(ping.__class__, TenantTask))

    def test_missing_tenant_id_fails(self):
        with self.assertRaises(ValueError):
            probe_tenant.delay().get()

    def test_unknown_tenant_fails(self):
        with self.assertRaises(ValueError):
            probe_tenant.delay(tenant_id=999999).get()

    def test_suspended_tenant_fails(self):
        self.tenant.status = Tenant.Status.SUSPENDED
        self.tenant.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            probe_tenant.delay(tenant_id=self.tenant.pk).get()

    def test_active_tenant_runs_body(self):
        self.assertEqual(probe_tenant.delay(tenant_id=self.tenant.pk).get(), "demo")
