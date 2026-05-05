from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Base class for role-based permissions. Subclasses set `allowed_roles`."""

    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdmin(RolePermission):
    allowed_roles = ("administrator",)


class IsAdminOrModerator(RolePermission):
    allowed_roles = ("administrator", "moderator")


class IsTeacher(RolePermission):
    allowed_roles = ("teacher",)


class IsTeacherOrAdmin(RolePermission):
    allowed_roles = ("teacher", "administrator")


class IsStudent(RolePermission):
    allowed_roles = ("student",)


class IsOwnerOrAdmin(BasePermission):
    """Grants access if the requesting user owns the object or is an administrator.

    The object is expected to have a `user` attribute or to be the user itself.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == "administrator":
            return True
        owner = getattr(obj, "user", obj)
        return owner == request.user
