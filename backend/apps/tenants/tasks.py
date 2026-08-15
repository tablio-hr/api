from celery import Task, shared_task

from apps.tenants.models import Tenant


class TenantTask(Task):
    """Mandatory tenant Celery pattern. Requires explicit tenant_id. No current-tenant."""

    abstract = True

    def __call__(self, *args, **kwargs):
        if "tenant_id" not in kwargs:
            raise ValueError("tenant_id is required")
        tenant_id = kwargs["tenant_id"]
        try:
            tenant = Tenant.operator_objects.get(pk=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise ValueError("tenant not found") from exc
        if tenant.status != Tenant.Status.ACTIVE:
            raise ValueError("tenant not active")
        self.tenant = tenant
        return super().__call__(*args, **kwargs)


@shared_task(base=TenantTask, bind=True)
def probe_tenant(self, **kwargs) -> str:
    """Test/ops probe that the TenantTask guard ran. Not a domain workflow."""
    return self.tenant.slug
