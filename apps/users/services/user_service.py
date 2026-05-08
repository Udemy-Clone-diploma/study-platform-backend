from django.db import transaction

from apps.users.constants import DEFAULT_TOP_TEACHERS_LIMIT
from apps.users.exceptions import ProfileNotAvailableError
from apps.users.models import TeacherProfile, User
from apps.users.serializers import (
    PROFILE_MODELS,
    PROFILE_SERIALIZERS,
    TopTeacherSerializer,
)


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

        # Refresh the reverse-OneToOne cache so a subsequent
        # user.{role}_profile read returns the just-saved profile.
        setattr(user, f"{user.role}_profile", profile)

        return user

    @staticmethod
    def get_top_teachers(
        limit: int = DEFAULT_TOP_TEACHERS_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        teachers = (
            TeacherProfile.objects.select_related("user")
            .filter(
                user__is_deleted=False,
                user__is_blocked=False,
                user__is_email_verified=True,
                user__role=User.RoleChoices.TEACHER,
            )
            .order_by("-rating", "-id")[:limit]
        )
        return TopTeacherSerializer(teachers, many=True, context=context or {}).data
