from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.identity.models import (
    LocationAssignment,
    MembershipEpisode,
    RoleAssignment,
    StaffMembership,
    UserIdentity,
)
from apps.identity.services import bootstrap_tenant, seed_stage_tenants
from apps.tenants.models import BusinessLocation, StorageArea, Tenant


class BootstrapTenantTests(TestCase):
    def test_bootstrap_creates_admin_chain(self):
        result = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="Admin@Demo.HR",
            admin_name="Admin",
            admin_password="secret-pass",
            location_names=["Front"],
        )
        self.assertTrue(result.created_tenant)
        self.assertTrue(result.password_set)
        self.assertIsNone(result.generated_password)
        self.assertEqual(result.identity.primary_login, "admin@demo.hr")
        self.assertTrue(result.identity.check_password("secret-pass"))
        self.assertEqual(StaffMembership.objects.filter(tenant=result.tenant).count(), 1)
        self.assertEqual(result.episode.status, result.episode.Status.ACTIVE)
        self.assertEqual(LocationAssignment.objects.filter(membership_episode=result.episode).count(), 1)
        self.assertEqual(RoleAssignment.objects.filter(membership_episode=result.episode).count(), 1)
        location = BusinessLocation.objects.get(tenant=result.tenant, name="Front")
        self.assertTrue(StorageArea.objects.filter(location=location, code=StorageArea.CODE_MAIN).exists())

    def test_bootstrap_is_idempotent_and_keeps_password(self):
        first = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="first-pass",
            location_names=["Front"],
        )
        second = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="second-pass",
            location_names=["Front"],
        )
        self.assertFalse(second.created_tenant)
        self.assertFalse(second.password_set)
        first.identity.refresh_from_db()
        self.assertTrue(first.identity.check_password("first-pass"))
        self.assertEqual(Tenant.objects.filter(slug="demo-a").count(), 1)
        self.assertEqual(BusinessLocation.objects.filter(tenant=first.tenant).count(), 1)

    def test_reset_admin_password_flag(self):
        bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="first-pass",
            location_names=["Front"],
        )
        result = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="second-pass",
            location_names=["Front"],
            reset_admin_password=True,
        )
        self.assertTrue(result.password_set)
        result.identity.refresh_from_db()
        self.assertTrue(result.identity.check_password("second-pass"))

    def test_bootstrap_after_ended_episode_increments_version(self):
        first = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="first-pass",
            location_names=["Front"],
        )
        first.episode.status = MembershipEpisode.Status.ENDED
        first.episode.valid_until = first.episode.valid_from + timedelta(seconds=1)
        first.episode.save(update_fields=["status", "valid_until", "updated_at"])

        second = bootstrap_tenant(
            slug="demo-a",
            name="Demo A",
            timezone_name="Europe/Zagreb",
            admin_login="admin@demo.hr",
            admin_name="Admin",
            admin_password="first-pass",
            location_names=["Front"],
        )
        self.assertEqual(second.episode.version, 2)
        self.assertEqual(second.episode.status, MembershipEpisode.Status.ACTIVE)
        self.assertEqual(
            MembershipEpisode.objects.filter(staff_membership=first.membership).count(),
            2,
        )


class SeedStageTenantsTests(TestCase):
    def test_seed_creates_both_tenants_and_three_locations(self):
        results = seed_stage_tenants(
            passwords={
                "SEED_ADMIN_PASSWORD_SIBENIK_1983": "mozart-pass",
                "SEED_ADMIN_PASSWORD_SUPINA_POLJICA": "uzorita-pass",
            }
        )
        self.assertEqual(len(results), 2)
        sibenik = Tenant.objects.get(slug="sibenik-1983")
        self.assertEqual(
            set(BusinessLocation.objects.filter(tenant=sibenik).values_list("name", flat=True)),
            {"Caffe Bar Mozart", "Dvorana Baldekin"},
        )
        self.assertEqual(BusinessLocation.objects.filter(tenant__slug="supina-poljica").count(), 1)
        natalija = UserIdentity.objects.get(primary_login="mozartsibenik@gmail.com")
        self.assertTrue(natalija.check_password("mozart-pass"))

    def test_seed_changed_env_password_does_not_reset(self):
        seed_stage_tenants(passwords={"SEED_ADMIN_PASSWORD_SIBENIK_1983": "one"})
        seed_stage_tenants(passwords={"SEED_ADMIN_PASSWORD_SIBENIK_1983": "two"})
        natalija = UserIdentity.objects.get(primary_login="mozartsibenik@gmail.com")
        self.assertTrue(natalija.check_password("one"))
        self.assertFalse(natalija.check_password("two"))

    @override_settings(TABLIO_API_HOST="api.tablio.hr")
    def test_command_refuses_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_stage_tenants")
