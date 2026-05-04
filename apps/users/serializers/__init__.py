from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile

from .EmailRequestSerializer import EmailRequestSerializer
from .LoginSerializer import LoginSerializer
from .ModeratorProfileSerializer import ModeratorProfileSerializer
from .PasswordResetConfirmSerializer import PasswordResetConfirmSerializer
from .RefreshTokenSerializer import RefreshTokenSerializer
from .StudentProfileSerializer import StudentProfileSerializer
from .TeacherProfileSerializer import TeacherProfileSerializer
from .UserRegistrationSerializer import UserRegistrationSerializer
from .UserSerializer import PROFILE_SERIALIZERS, UserSerializer
from .UserUpdateSerializer import UserUpdateSerializer

PROFILE_MODELS = {
    "student": StudentProfile,
    "teacher": TeacherProfile,
    "moderator": ModeratorProfile,
}

__all__ = [
    "EmailRequestSerializer",
    "LoginSerializer",
    "ModeratorProfileSerializer",
    "PasswordResetConfirmSerializer",
    "PROFILE_MODELS",
    "PROFILE_SERIALIZERS",
    "RefreshTokenSerializer",
    "StudentProfileSerializer",
    "TeacherProfileSerializer",
    "UserRegistrationSerializer",
    "UserSerializer",
    "UserUpdateSerializer",
]
