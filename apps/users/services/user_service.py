from django.db import transaction

from apps.users.exceptions import ProfileNotAvailableError
from apps.users.models import User
from apps.users.serializers import PROFILE_MODELS, PROFILE_SERIALIZERS


class UserService:
    @staticmethod
    @transaction.atomic
    def soft_delete_user(user: User) -> None:
        user.is_deleted = True
        user.status = "inactive"
        user.save(update_fields=["is_deleted", "status"])

    @staticmethod
    @transaction.atomic
    def set_block_status(user: User, is_blocked: bool = True) -> User:
        user.is_blocked = is_blocked
        user.status = "inactive" if is_blocked else "active"
        user.save(update_fields=["is_blocked", "status"])
        return user

    @staticmethod
    @transaction.atomic
    def update_profile(user: User, data: dict, partial: bool = True) -> User:
        serializer_class = PROFILE_SERIALIZERS.get(user.role)
        profile_model = PROFILE_MODELS.get(user.role)

        if not serializer_class or not profile_model:
            raise ProfileNotAvailableError(
                "Profile is not available for this role."
            )

        profile, _ = profile_model.objects.get_or_create(user=user)

        serializer = serializer_class(profile, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return user
