from rest_framework.permissions import BasePermission

from apps.users.models import User


class IsCourseOwnerOrAdmin(BasePermission):
    """Allows access if the user is the course's teacher or an administrator."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == User.RoleChoices.ADMINISTRATOR:
            return True
        return obj.teacher_profile.user_id == user.id
