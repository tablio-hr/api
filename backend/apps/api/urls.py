from django.urls import path

from apps.api.location_views import LocationDeactivateView, LocationDetailView, LocationListCreateView
from apps.api.staff_command_views import (
    EpisodeActivateView,
    EpisodeEndView,
    EpisodeSuspendView,
    LocationAssignmentCreateView,
    LocationAssignmentRevokeView,
    RoleAssignmentCreateView,
    RoleAssignmentRevokeView,
    StaffMembershipCreateView,
)
from apps.api.staff_views import MeContextView, StaffLoginView, StaffLogoutView
from apps.api.views import AppConfigView, ScopeProbeView

urlpatterns = [
    path("auth/staff/login", StaffLoginView.as_view(), name="staff-login"),
    path("auth/staff/logout", StaffLogoutView.as_view(), name="staff-logout"),
    path("me/context", MeContextView.as_view(), name="me-context"),
    path("locations", LocationListCreateView.as_view(), name="location-list"),
    path("locations/<uuid:public_id>", LocationDetailView.as_view(), name="location-detail"),
    path("locations/<uuid:public_id>:deactivate", LocationDeactivateView.as_view(), name="location-deactivate"),
    path("staff/memberships", StaffMembershipCreateView.as_view(), name="staff-membership-create"),
    path(
        "staff/memberships/<uuid:membership_id>/episodes:activate",
        EpisodeActivateView.as_view(),
        name="staff-episode-activate",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/episodes:suspend",
        EpisodeSuspendView.as_view(),
        name="staff-episode-suspend",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/episodes:end",
        EpisodeEndView.as_view(),
        name="staff-episode-end",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/location-assignments",
        LocationAssignmentCreateView.as_view(),
        name="staff-location-assignment-create",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/location-assignments/<uuid:assignment_id>:revoke",
        LocationAssignmentRevokeView.as_view(),
        name="staff-location-assignment-revoke",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/role-assignments",
        RoleAssignmentCreateView.as_view(),
        name="staff-role-assignment-create",
    ),
    path(
        "staff/memberships/<uuid:membership_id>/role-assignments/<uuid:assignment_id>:revoke",
        RoleAssignmentRevokeView.as_view(),
        name="staff-role-assignment-revoke",
    ),
    path("app/config", AppConfigView.as_view(), name="app-config"),
    path("app/scope-probe", ScopeProbeView.as_view(), name="scope-probe"),
]
