COMPOSITE_FOREIGN_KEYS = (
    {
        "table": "tenants_storagearea",
        "name": "tenants_storage_location_tenant_fk",
        "columns": ("location_id", "tenant_id"),
        "target": "tenants_businesslocation",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_membershipepisode",
        "name": "identity_episode_membership_tenant_fk",
        "columns": ("staff_membership_id", "tenant_id"),
        "target": "identity_staffmembership",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_locationassignment",
        "name": "identity_loc_assign_membership_tenant_fk",
        "columns": ("staff_membership_id", "tenant_id"),
        "target": "identity_staffmembership",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_locationassignment",
        "name": "identity_loc_assign_episode_tenant_fk",
        "columns": ("membership_episode_id", "tenant_id"),
        "target": "identity_membershipepisode",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_locationassignment",
        "name": "identity_loc_assign_location_tenant_fk",
        "columns": ("location_id", "tenant_id"),
        "target": "tenants_businesslocation",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_roleassignment",
        "name": "identity_role_assign_membership_tenant_fk",
        "columns": ("staff_membership_id", "tenant_id"),
        "target": "identity_staffmembership",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_roleassignment",
        "name": "identity_role_assign_episode_tenant_fk",
        "columns": ("membership_episode_id", "tenant_id"),
        "target": "identity_membershipepisode",
        "target_columns": ("id", "tenant_id"),
    },
    {
        "table": "identity_roleassignment",
        "name": "identity_role_assign_location_tenant_fk",
        "columns": ("location_id", "tenant_id"),
        "target": "tenants_businesslocation",
        "target_columns": ("id", "tenant_id"),
    },
)


def _add_sql(spec: dict) -> str:
    cols = ", ".join(spec["columns"])
    refs = ", ".join(spec["target_columns"])
    return (
        f'ALTER TABLE "{spec["table"]}" ADD CONSTRAINT "{spec["name"]}" '
        f"FOREIGN KEY ({cols}) REFERENCES \"{spec['target']}\" ({refs})"
    )


def _drop_sql(spec: dict) -> str:
    return f'ALTER TABLE "{spec["table"]}" DROP CONSTRAINT IF EXISTS "{spec["name"]}"'


def apply_composite_foreign_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for spec in COMPOSITE_FOREIGN_KEYS:
            cursor.execute(_add_sql(spec))


def drop_composite_foreign_keys(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for spec in reversed(COMPOSITE_FOREIGN_KEYS):
            cursor.execute(_drop_sql(spec))
