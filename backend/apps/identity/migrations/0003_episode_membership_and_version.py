from django.db import migrations, models

from apps.tenants.composite_fks import (
    apply_episode_membership_foreign_keys,
    drop_episode_membership_foreign_keys,
)


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0002_composite_tenant_fks"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="membershipepisode",
            constraint=models.UniqueConstraint(
                fields=("id", "staff_membership", "tenant"),
                name="identity_episode_unique_id_membership_tenant",
            ),
        ),
        migrations.AddConstraint(
            model_name="membershipepisode",
            constraint=models.UniqueConstraint(
                fields=("staff_membership", "version"),
                name="identity_episode_unique_membership_version",
            ),
        ),
        migrations.RunPython(
            apply_episode_membership_foreign_keys,
            drop_episode_membership_foreign_keys,
        ),
    ]
