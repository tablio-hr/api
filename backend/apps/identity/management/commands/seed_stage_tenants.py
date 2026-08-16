import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.identity.services import STAGE_TENANTS, seed_stage_tenants


class Command(BaseCommand):
    help = "Idempotent stage seed for ŠIBENIK 1983 and ŠUPINA POLJICA. Refuses production."

    def add_arguments(self, parser):
        parser.add_argument("--reset-admin-password", action="store_true")

    def handle(self, *args, **options):
        host = getattr(settings, "TABLIO_API_HOST", "")
        if host == "api.tablio.hr":
            raise CommandError("seed_stage_tenants refuses production.")

        passwords = {spec["password_env"]: os.environ.get(spec["password_env"]) or None for spec in STAGE_TENANTS}
        results = seed_stage_tenants(
            passwords=passwords,
            reset_admin_password=options["reset_admin_password"],
        )
        for spec, result in zip(STAGE_TENANTS, results, strict=True):
            self.stdout.write(self.style.SUCCESS(f"Seeded {result.tenant.slug}."))
            if result.generated_password:
                self.stdout.write(
                    self.style.WARNING(
                        f"Copy {spec['admin_login']} password now — it will not be shown again:\n"
                    )
                )
                self.stdout.write(result.generated_password)
            elif not result.password_set:
                self.stdout.write(f"Existing password for {spec['admin_login']} left unchanged.")
