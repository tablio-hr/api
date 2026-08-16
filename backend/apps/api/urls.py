from django.urls import path

from apps.api.staff_views import MeContextView, StaffLoginView, StaffLogoutView
from apps.api.views import AppConfigView, ScopeProbeView

urlpatterns = [
    path("auth/staff/login", StaffLoginView.as_view(), name="staff-login"),
    path("auth/staff/logout", StaffLogoutView.as_view(), name="staff-logout"),
    path("me/context", MeContextView.as_view(), name="me-context"),
    path("app/config", AppConfigView.as_view(), name="app-config"),
    path("app/scope-probe", ScopeProbeView.as_view(), name="scope-probe"),
]
