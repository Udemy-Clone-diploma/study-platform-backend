from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.users.models import User


class CanCreateArticle(BasePermission):
    """Only teachers, moderators and administrators may author blog articles."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role
            in (
                User.RoleChoices.TEACHER,
                User.RoleChoices.MODERATOR,
                User.RoleChoices.ADMINISTRATOR,
            )
        )


class CanManageArticle(BasePermission):
    """Moderators/admins can manage any article; teachers only their own.

    This is a coarse "may touch this object at all" gate, the finer status
    transition rules (e.g. an author can't edit a published article without
    withdrawing it first) live in ArticleService and raise BlogError (-> 409).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role in (User.RoleChoices.MODERATOR, User.RoleChoices.ADMINISTRATOR):
            return True
        return obj.author_id == user.id
