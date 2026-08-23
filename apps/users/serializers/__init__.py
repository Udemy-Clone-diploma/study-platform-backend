from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile

from .AdminNoteSerializer import AdminNoteSerializer
from .AdminUserCreateSerializer import AdminUserCreateSerializer
from .AdminUserUpdateSerializer import AdminUserUpdateSerializer
from .ChangePasswordSerializer import ChangePasswordSerializer
from .EmailRequestSerializer import EmailRequestSerializer
from .GoogleLoginSerializer import GoogleLoginSerializer
from .LoginSerializer import LoginSerializer
from .ModeratorProfileSerializer import ModeratorProfileSerializer
from .PasswordResetConfirmSerializer import PasswordResetConfirmSerializer
from .PublicModeratorProfileSerializer import PublicModeratorProfileSerializer
from .PublicStudentProfileSerializer import PublicStudentProfileSerializer
from .PublicTeacherProfileSerializer import PublicTeacherProfileSerializer
from .PublicUserSerializer import PublicUserSerializer
from .RefreshTokenSerializer import RefreshTokenSerializer
from .StudentProfileSerializer import StudentProfileSerializer
from .TeacherProfileSerializer import TeacherProfileSerializer
from .TeacherApplicationCreateSerializer import TeacherApplicationCreateSerializer
from .TeacherApplicationDecisionSerializer import TeacherApplicationDecisionSerializer
from .TeacherApplicationSerializer import TeacherApplicationSerializer
from .UserRegistrationSerializer import UserRegistrationSerializer
from .UserReportCreateSerializer import UserReportCreateSerializer
from .UserReportParticipantSerializer import UserReportParticipantSerializer
from .UserReportActionSerializer import UserReportActionSerializer
from .UserReportSerializer import UserReportSerializer
from .ModeratorUserReportActionSerializer import ModeratorUserReportActionSerializer
from .AdminUserReportActionSerializer import AdminUserReportActionSerializer
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
    "GoogleLoginSerializer",
    "LoginSerializer",
    "ModeratorProfileSerializer",
    "PasswordResetConfirmSerializer",
    "PublicModeratorProfileSerializer",
    "PublicStudentProfileSerializer",
    "PublicTeacherProfileSerializer",
    "PublicUserSerializer",
    "PROFILE_MODELS",
    "PROFILE_SERIALIZERS",
    "RefreshTokenSerializer",
    "StudentProfileSerializer",
    "TeacherProfileSerializer",
    "TeacherApplicationCreateSerializer",
    "TeacherApplicationDecisionSerializer",
    "TeacherApplicationSerializer",
    "UserRegistrationSerializer",
    "UserReportCreateSerializer",
    "UserReportParticipantSerializer",
    "UserReportActionSerializer",
    "UserReportSerializer",
    "ModeratorUserReportActionSerializer",
    "AdminUserReportActionSerializer",
    "UserBlockSerializer",
    "UserSerializer",
    "UserUpdateSerializer",
    "TopTeacherSerializer",
]
