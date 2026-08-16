from django.db import migrations

from apps.tenants.composite_fks import apply_composite_foreign_keys, drop_composite_foreign_keys


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0001_initial"),
        ("tenants", "0002_public_id_location_storage"),
    ]

    operations = [
        migrations.RunPython(apply_composite_foreign_keys, drop_composite_foreign_keys),
    ]
