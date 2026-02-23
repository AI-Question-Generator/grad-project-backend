from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class IsTeacher(permissions.BasePermission):
    """
    Allow access only to users with teacher role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.TEACHER

class IsStudent(permissions.BasePermission):
    """
    Allow access only to users with student role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.STUDENT

class IsAdmin(permissions.BasePermission):
    """
    Allow access only to users with admin role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.ADMIN

class IsTeacherOrAdmin(permissions.BasePermission):
    """
    Allow access to users with teacher or admin role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in [User.TEACHER, User.ADMIN]
