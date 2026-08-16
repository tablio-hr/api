from unittest import skipUnless

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from apps.identity.models import (
    AssignmentStatus,
    LocationAssignment,
    MembershipEpisode,
    RoleAssignment,
    ScopeType,
    StaffMembership,
    UserIdentity,
)
from apps.identity.services import ensure_system_roles
from apps.tenants.models import BusinessLocation, StorageArea, Tenant
from apps.tenants.services import create_business_location, get_or_create_business_location


class LocationStorageTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo A", slug="demo-a", timezone="Europe/Zagreb")

    def test_create_location_seeds_main_storage(self):
        location = create_business_location(
            tenant=self.tenant,
            name="Caffe Bar Mozart",
            timezone="Europe/Zagreb",
        )
        main = StorageArea.objects.get(location=location, code=StorageArea.CODE_MAIN)
        self.assertTrue(main.is_default)
        self.assertEqual(main.tenant_id, self.tenant.pk)

    def test_get_or_create_does_not_duplicate_main(self):
        first, created = get_or_create_business_location(
            tenant=self.tenant,
            name="Caffe Bar Mozart",
            timezone="Europe/Zagreb",
        )
        self.assertTrue(created)
        second, created_again = get_or_create_business_location(
            tenant=self.tenant,
            name="caffe bar mozart",
            timezone="Europe/Zagreb",
        )
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(StorageArea.objects.filter(location=first, code=StorageArea.CODE_MAIN).count(), 1)

    def test_duplicate_location_name_rejected(self):
        create_business_location(tenant=self.tenant, name="Mozart", timezone="Europe/Zagreb")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BusinessLocation.objects.create(
                    tenant=self.tenant,
                    name="mozart",
                    timezone="Europe/Zagreb",
                )


class MembershipConstraintTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo A", slug="demo-a")
        self.other = Tenant.objects.create(name="Demo B", slug="demo-b")
        self.identity = UserIdentity(name="Ada", primary_login="Ada@X.HR", status=UserIdentity.Status.ACTIVE)
        self.identity.set_password("secret")
        self.identity.save()

    def test_login_stored_normalized_and_unique(self):
        self.assertEqual(self.identity.primary_login, "ada@x.hr")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserIdentity.objects.create(
                    name="Ada 2",
                    primary_login="ADA@x.hr",
                    status=UserIdentity.Status.ACTIVE,
                    password="x",
                )

    def test_second_membership_same_tenant_identity_rejected(self):
        StaffMembership.objects.create(
            tenant=self.tenant,
            user_identity=self.identity,
            staff_number="1",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StaffMembership.objects.create(
                    tenant=self.tenant,
                    user_identity=self.identity,
                    staff_number="2",
                )

    def test_same_person_two_tenants_allowed(self):
        StaffMembership.objects.create(tenant=self.tenant, user_identity=self.identity, staff_number="1")
        StaffMembership.objects.create(tenant=self.other, user_identity=self.identity, staff_number="1")
        self.assertEqual(StaffMembership.objects.filter(user_identity=self.identity).count(), 2)

    def test_one_current_episode(self):
        membership = StaffMembership.objects.create(
            tenant=self.tenant,
            user_identity=self.identity,
            staff_number="1",
        )
        now = timezone.now()
        MembershipEpisode.objects.create(
            tenant=self.tenant,
            staff_membership=membership,
            version=1,
            status=MembershipEpisode.Status.ACTIVE,
            valid_from=now,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MembershipEpisode.objects.create(
                    tenant=self.tenant,
                    staff_membership=membership,
                    version=2,
                    status=MembershipEpisode.Status.INVITED,
                    valid_from=now,
                )


class AssignmentScopeTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo A", slug="demo-a")
        self.identity = UserIdentity.objects.create(
            name="Ada",
            primary_login="ada@x.hr",
            status=UserIdentity.Status.ACTIVE,
            password="x",
        )
        self.membership = StaffMembership.objects.create(
            tenant=self.tenant,
            user_identity=self.identity,
            staff_number="1",
        )
        self.episode = MembershipEpisode.objects.create(
            tenant=self.tenant,
            staff_membership=self.membership,
            version=1,
            status=MembershipEpisode.Status.ACTIVE,
            valid_from=timezone.now(),
        )
        self.location = create_business_location(
            tenant=self.tenant,
            name="Mozart",
            timezone="Europe/Zagreb",
        )

    def test_tenant_scope_rejects_location_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LocationAssignment.objects.create(
                    tenant=self.tenant,
                    staff_membership=self.membership,
                    membership_episode=self.episode,
                    scope_type=ScopeType.TENANT,
                    location=self.location,
                    status=AssignmentStatus.ACTIVE,
                    valid_from=timezone.now(),
                )

    def test_location_scope_requires_location_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LocationAssignment.objects.create(
                    tenant=self.tenant,
                    staff_membership=self.membership,
                    membership_episode=self.episode,
                    scope_type=ScopeType.LOCATION,
                    location=None,
                    status=AssignmentStatus.ACTIVE,
                    valid_from=timezone.now(),
                )


@skipUnless(connection.vendor == "postgresql", "Composite tenant FKs are PostgreSQL-only.")
class CompositeTenantFKTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Demo A", slug="demo-a")
        self.tenant_b = Tenant.objects.create(name="Demo B", slug="demo-b")
        self.identity = UserIdentity.objects.create(
            name="Ada",
            primary_login="ada@x.hr",
            status=UserIdentity.Status.ACTIVE,
            password="x",
        )
        self.membership_a = StaffMembership.objects.create(
            tenant=self.tenant_a,
            user_identity=self.identity,
            staff_number="1",
        )
        self.episode_a = MembershipEpisode.objects.create(
            tenant=self.tenant_a,
            staff_membership=self.membership_a,
            version=1,
            status=MembershipEpisode.Status.ACTIVE,
            valid_from=timezone.now(),
        )
        self.location_b = create_business_location(
            tenant=self.tenant_b,
            name="Uzorita",
            timezone="Europe/Zagreb",
        )
        self.role_version = ensure_system_roles()

    def test_location_from_other_tenant_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LocationAssignment.objects.create(
                    tenant=self.tenant_a,
                    staff_membership=self.membership_a,
                    membership_episode=self.episode_a,
                    scope_type=ScopeType.LOCATION,
                    location=self.location_b,
                    status=AssignmentStatus.ACTIVE,
                    valid_from=timezone.now(),
                )

    def test_role_location_from_other_tenant_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoleAssignment.objects.create(
                    tenant=self.tenant_a,
                    staff_membership=self.membership_a,
                    membership_episode=self.episode_a,
                    role_version=self.role_version,
                    scope_type=ScopeType.LOCATION,
                    location=self.location_b,
                    status=AssignmentStatus.ACTIVE,
                    valid_from=timezone.now(),
                )
