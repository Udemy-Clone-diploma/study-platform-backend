from django.db import transaction
from django.utils import timezone

from apps.users.exceptions import ApplicationAlreadyDecidedError
from apps.users.messages import TeacherApplicationMessages
from apps.users.models import TeacherApplication, User
from apps.users.services.email_service import EmailService
from apps.users.services.user_service import UserService


class TeacherApplicationService:
    @staticmethod
    def email_conflict(email: str) -> str | None:
        """Returns the reason the email can't be used to apply, or None if it's free."""
        if User.all_objects.filter(email__iexact=email).exists():
            return TeacherApplicationMessages.EMAIL_ALREADY_REGISTERED
        if TeacherApplication.objects.filter(
            email__iexact=email,
            status__in=[
                TeacherApplication.StatusChoices.PENDING,
                TeacherApplication.StatusChoices.APPROVED,
            ],
        ).exists():
            return TeacherApplicationMessages.DUPLICATE_APPLICATION
        return None

    @staticmethod
    def submit(validated_data: dict) -> TeacherApplication:
        directions = validated_data.pop("directions", [])
        application = TeacherApplication.objects.create(**validated_data)
        application.directions.set(directions)
        return application

    @staticmethod
    def _ensure_pending(application: TeacherApplication) -> None:
        if application.status != TeacherApplication.StatusChoices.PENDING:
            raise ApplicationAlreadyDecidedError(
                "This application has already been decided."
            )

    @classmethod
    @transaction.atomic
    def approve(cls, application: TeacherApplication, moderator_profile, comment: str = "") -> User:
        cls._ensure_pending(application)

        user = User(
            email=application.email,
            first_name=application.first_name,
            last_name=application.last_name,
            role=User.RoleChoices.TEACHER,
            status=User.StatusChoices.INACTIVE,
            is_email_verified=False,
        )
        user.set_unusable_password()
        user.save()

        UserService.ensure_profile(user)
        teacher_profile = user.teacher_profile
        teacher_profile.bio = application.bio
        teacher_profile.experience = application.experience
        teacher_profile.specialization = application.specialization
        teacher_profile.years_experience = application.years_experience
        teacher_profile.save()

        application.status = TeacherApplication.StatusChoices.APPROVED
        application.moderator_profile = moderator_profile
        application.moderator_comment = comment
        application.decided_at = timezone.now()
        application.created_user = user
        application.save()

        EmailService.send_teacher_invitation_email(user)
        return user

    @classmethod
    @transaction.atomic
    def cancel(cls, application: TeacherApplication, moderator_profile, comment: str = "") -> TeacherApplication:
        cls._ensure_pending(application)

        application.status = TeacherApplication.StatusChoices.CANCELLED
        application.moderator_profile = moderator_profile
        application.moderator_comment = comment
        application.decided_at = timezone.now()
        application.save()

        EmailService.send_teacher_application_cancelled_email(application)
        return application
