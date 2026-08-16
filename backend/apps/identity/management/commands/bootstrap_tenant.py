from django.core.management.base import BaseCommand

from apps.identity.services import bootstrap_tenant


class Command(BaseCommand):
    help = "Create a tenant, first TENANT_ADMIN, and locations. Platform path only."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--timezone", default="Europe/Zagreb")
        parser.add_argument("--admin-login", required=True)
        parser.add_argument("--admin-name", required=True)
        parser.add_argument("--admin-password", default=None)
        parser.add_argument("--location", action="append", dest="locations", required=True)
        parser.add_argument("--staff-number", default="1")
        parser.add_argument("--reset-admin-password", action="store_true")

    def handle(self, *args, **options):
        result = bootstrap_tenant(
            slug=options["slug"],
            name=options["name"],
            timezone_name=options["timezone"],
            admin_login=options["admin_login"],
            admin_name=options["admin_name"],
            admin_password=options["admin_password"],
            location_names=options["locations"],
            staff_number=options["staff_number"],
            reset_admin_password=options["reset_admin_password"],
        )
        self.stdout.write(self.style.SUCCESS(f"Tenant {result.tenant.slug} ready."))
        if result.generated_password:
            self.stdout.write(self.style.WARNING("Copy this admin password now — it will not be shown again:\n"))
            self.stdout.write(result.generated_password)
        elif result.password_set:
            self.stdout.write("Admin password was set from the provided value.")
        else:
            self.stdout.write("Existing admin password left unchanged.")
