from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile

from .AdminNoteSerializer import AdminNoteSerializer
from .AdminUserCreateSerializer import AdminUserCreateSerializer
from .AdminUserUpdateSerializer import AdminUserUpdateSerializer
from .ChangePasswordSerializer import ChangePasswordSerializer
from .EmailRequestSerializer import EmailRequestSerializer
from .LoginSerializer import LoginSerializer
from .ModeratorProfileSerializer import ModeratorProfileSerializer
from .PasswordResetConfirmSerializer import PasswordResetConfirmSerializer
from .RefreshTokenSerializer import RefreshTokenSerializer
from .StudentProfileSerializer import StudentProfileSerializer
from .TeacherProfileSerializer import TeacherProfileSerializer
from .TeacherApplicationCreateSerializer import TeacherApplicationCreateSerializer
from .TeacherApplicationDecisionSerializer import TeacherApplicationDecisionSerializer
from .TeacherApplicationSerializer import TeacherApplicationSerializer
from .UserRegistrationSerializer import UserRegistrationSerializer
from .UserBlockSerializer import UserBlockSerializer
from .UserSerializer import PROFILE_SERIALIZERS, UserSerializer
from .UserUpdateSerializer import UserUpdateSerializer
from .TopTeacherSerializer import TopTeacherSerializer

PROFILE_MODELS = {
    "student": StudentProfile,
    "teacher": TeacherProfile,
    "moderator": ModeratorProfile,
}

__all__ = [
    "AdminNoteSerializer",
    "AdminUserCreateSerializer",
    "AdminUserUpdateSerializer",
    "ChangePasswordSerializer",
    "EmailRequestSerializer",
    "LoginSerializer",
    "ModeratorProfileSerializer",
    "PasswordResetConfirmSerializer",
    "PROFILE_MODELS",
    "PROFILE_SERIALIZERS",
    "RefreshTokenSerializer",
    "StudentProfileSerializer",
    "TeacherProfileSerializer",
    "TeacherApplicationCreateSerializer",
    "TeacherApplicationDecisionSerializer",
    "TeacherApplicationSerializer",
    "UserRegistrationSerializer",
    "UserBlockSerializer",
    "UserSerializer",
    "UserUpdateSerializer",
    "TopTeacherSerializer",
]
