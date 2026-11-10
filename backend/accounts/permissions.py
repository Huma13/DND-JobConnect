from rest_framework.permissions import BasePermission

from .models import User


class IsAdminRole(BasePermission):
    """SRS 6.5: only users with the admin role get through; everyone else gets 403."""

    message = "Admin role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
