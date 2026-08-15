from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import VALID_SCOPES, ApiApplication, Tenant


class Command(BaseCommand):
    help = "Create an API application and print the raw token once."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant slug")
        parser.add_argument("--name", required=True, help="Application display name")
        parser.add_argument(
            "--scopes",
            default="public:read",
            help="Comma-separated scopes.",
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options["tenant"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{options['tenant']}' not found.") from exc

        scopes = [s.strip() for s in options["scopes"].split(",") if s.strip()]
        invalid = set(scopes) - VALID_SCOPES
        if invalid:
            raise CommandError(f"Unknown scopes: {', '.join(sorted(invalid))}")

        application, raw_token = ApiApplication.create_with_token(
            tenant=tenant,
            name=options["name"],
            scopes=scopes,
        )
        self.stdout.write(self.style.SUCCESS(f"Created API application: {application.name}"))
        self.stdout.write(self.style.WARNING("Copy this token now — it will not be shown again:\n"))
        self.stdout.write(raw_token)
