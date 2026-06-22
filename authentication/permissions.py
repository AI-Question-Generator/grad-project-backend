from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class IsMember(permissions.BasePermission):
    """Allow access only to users with member role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.MEMBER
        )

class IsAdmin(permissions.BasePermission):
    """Allow access only to users with admin role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ADMIN
        )

class IsMemberOrAdmin(permissions.BasePermission):
    """Allow access to users with member or admin role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [User.MEMBER, User.ADMIN]
        )
