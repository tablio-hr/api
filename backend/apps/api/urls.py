from django.urls import path

from apps.api.views import AppConfigView, ScopeProbeView

urlpatterns = [
    path("app/config", AppConfigView.as_view(), name="app-config"),
    path("app/scope-probe", ScopeProbeView.as_view(), name="scope-probe"),
]
