from django.urls import path

from apps.api.staff_views import MeContextView, StaffLoginView, StaffLogoutView
from apps.api.views import AppConfigView, ScopeProbeView
from apps.leads.views import EarlyAccessView

urlpatterns = [
    path("auth/staff/login", StaffLoginView.as_view(), name="staff-login"),
    path("auth/staff/logout", StaffLogoutView.as_view(), name="staff-logout"),
    path("me/context", MeContextView.as_view(), name="me-context"),
    path("app/config", AppConfigView.as_view(), name="app-config"),
    path("app/scope-probe", ScopeProbeView.as_view(), name="scope-probe"),
    path("early-access", EarlyAccessView.as_view(), name="early-access"),
]
