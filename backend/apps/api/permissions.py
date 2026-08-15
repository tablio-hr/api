from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission


class HasApiApplication(BasePermission):
    def has_permission(self, request, view) -> bool:
        if getattr(request, "api_application", None) is None:
            raise NotAuthenticated("Invalid API key.")
        return True


class HasRequiredScopes(BasePermission):
    def has_permission(self, request, view) -> bool:
        application = getattr(request, "api_application", None)
        if application is None:
            raise NotAuthenticated("Invalid API key.")
        required = getattr(view, "required_scopes", [])
        granted = set(application.scopes or [])
        return set(required).issubset(granted)
