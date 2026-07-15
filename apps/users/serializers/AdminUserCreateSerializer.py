from apps.users.models import StudentProfile, User

from .UserRegistrationSerializer import UserRegistrationSerializer


class AdminUserCreateSerializer(UserRegistrationSerializer):
    """Admin-only user creation: honors `role` and skips email verification.

    Public self-registration must keep using UserRegistrationSerializer,
    which pins role to student and requires the verification email.
    """

    def create(self, validated_data):
        password = validated_data.pop("password")
        date_of_birth = validated_data.pop("date_of_birth", None)
        user = User(is_email_verified=True, **validated_data)
        user.set_password(password)
        user.save()
        if user.role == User.RoleChoices.STUDENT:
            StudentProfile.objects.create(user=user, date_of_birth=date_of_birth)
        return user
