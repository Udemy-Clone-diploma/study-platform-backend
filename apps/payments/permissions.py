from rest_framework.permissions import BasePermission

from apps.users.models import User


class IsFinanceOperator(BasePermission):
    message = "Administrator or moderator access required."

    def has_permission(
        self,
        request,
        view,
    ) -> bool:
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.role
            in {
                User.RoleChoices.ADMINISTRATOR,
                User.RoleChoices.MODERATOR,
            }
        )
