import uuid

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


def fill_tenant_public_ids(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    for tenant in Tenant.objects.filter(public_id__isnull=True):
        tenant.public_id = uuid.uuid4()
        tenant.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(fill_tenant_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tenant",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.DeleteModel(name="TenantMembership"),
        migrations.CreateModel(
            name="BusinessLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("timezone", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="locations",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="StorageArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=64)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="storage_areas",
                        to="tenants.businesslocation",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="storage_areas",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={"ordering": ["location_id", "code"]},
        ),
        migrations.AddConstraint(
            model_name="businesslocation",
            constraint=models.UniqueConstraint(fields=("id", "tenant"), name="tenants_location_unique_id_tenant"),
        ),
        migrations.AddConstraint(
            model_name="businesslocation",
            constraint=models.UniqueConstraint(
                fields=("tenant", "public_id"),
                name="tenants_location_unique_tenant_public",
            ),
        ),
        migrations.AddConstraint(
            model_name="businesslocation",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                "tenant",
                name="tenants_location_unique_tenant_lname",
            ),
        ),
        migrations.AddConstraint(
            model_name="storagearea",
            constraint=models.UniqueConstraint(
                fields=("location", "code"),
                name="tenants_storage_unique_location_code",
            ),
        ),
        migrations.AddConstraint(
            model_name="storagearea",
            constraint=models.UniqueConstraint(
                fields=("location",),
                condition=models.Q(("is_default", True)),
                name="tenants_storage_one_default_per_location",
            ),
        ),
    ]
