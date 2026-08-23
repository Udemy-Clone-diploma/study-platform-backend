from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    AdminNoteView,
    ChangePasswordView,
    GoogleLoginView,
    LoginView,
    MeView,
    ModeratorProfileView,
    RegisterView,
    StudentProfileView,
    TeacherProfileView,
    TokenRefreshView,
    TopTeachersView,
    UserViewSet,
    UserSearchView,
    VerifyEmailView,
    ResendVerificationEmailView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordResetValidateView,
    PublicUserProfileView,
    AdminUserProfileView,
    UserReportView,
    UserReportUnassignedListView,
    UserReportMineListView,
    UserReportEscalatedListView,
    UserReportAllListView,
    UserReportClaimView,
    UserReportModeratorActionView,
    UserReportAdminActionView,
    ModeratorDashboardView,
    AdminModeratorDashboardView,
    TeacherInvitationConfirmView,
    TeacherInvitationValidateView,
    TeacherInvitationResendView,
    TeacherApplicationSubmitView,
    TeacherApplicationEmailCheckView,
    TeacherApplicationModerationViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")
router.register(r"teacher-applications", TeacherApplicationModerationViewSet, basename="teacher-applications")

urlpatterns = [
    path("users/top-teachers/", TopTeachersView.as_view(), name="top-teachers"),
    path("users/search/",       UserSearchView.as_view(),  name="user-search"),
    path(
        "users/<int:user_id>/public-profile/",
        PublicUserProfileView.as_view(),
        name="user-public-profile",
    ),
    path(
        "users/<int:user_id>/admin-profile/",
        AdminUserProfileView.as_view(),
        name="user-admin-profile",
    ),
    path(
        "users/<int:user_id>/report/",
        UserReportView.as_view(),
        name="user-report",
    ),
    path(
        "users/moderation/reports/unassigned/",
        UserReportUnassignedListView.as_view(),
        name="user-report-moderation-unassigned",
    ),
    path(
        "users/moderation/reports/mine/",
        UserReportMineListView.as_view(),
        name="user-report-moderation-mine",
    ),
    path(
        "users/moderation/reports/all/",
        UserReportAllListView.as_view(),
        name="user-report-moderation-all",
    ),
    path(
        "users/moderation/reports/escalated/",
        UserReportEscalatedListView.as_view(),
        name="user-report-moderation-escalated",
    ),
    path(
        "users/moderation/reports/<int:report_id>/claim/",
        UserReportClaimView.as_view(),
        name="user-report-moderation-claim",
    ),
    path(
        "users/moderation/reports/<int:report_id>/moderator-action/",
        UserReportModeratorActionView.as_view(),
        name="user-report-moderator-action",
    ),
    path(
        "users/moderation/reports/<int:report_id>/admin-action/",
        UserReportAdminActionView.as_view(),
        name="user-report-admin-action",
    ),
    path(
        "users/moderation/dashboard/",
        ModeratorDashboardView.as_view(),
        name="moderator-dashboard-statistics",
    ),
    path(
        "users/moderation/moderators/<int:user_id>/dashboard/",
        AdminModeratorDashboardView.as_view(),
        name="admin-moderator-dashboard-statistics",
    ),
    path("users/<int:user_id>/note/", AdminNoteView.as_view(), name="user-note"),
    path(
        "teacher-applications/submit/",
        TeacherApplicationSubmitView.as_view(),
        name="teacher-application-submit"),
    path(
        "teacher-applications/check-email/",
        TeacherApplicationEmailCheckView.as_view(),
        name="teacher-application-check-email"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/me/profile/teacher/", TeacherProfileView.as_view(), name="auth-me-profile-teacher"),
    path("auth/me/profile/student/", StudentProfileView.as_view(), name="auth-me-profile-student"),
    path("auth/me/profile/moderator/", ModeratorProfileView.as_view(), name="auth-me-profile-moderator"),
    path("", include(router.urls)),
    path(
        "auth/verify-email/<str:uidb64>/<str:token>/", 
        VerifyEmailView.as_view(), 
        name="auth-verify-email"),
    path(
        "auth/resend-verification/", 
        ResendVerificationEmailView.as_view(), 
        name="auth-resend-verification"),
    path(
        "auth/password-reset/", 
        PasswordResetRequestView.as_view(), 
        name="auth-password-reset"),
    path(
        "auth/password-reset/<str:uidb64>/<str:token>/", 
        PasswordResetConfirmView.as_view(), 
        name="auth-password-reset-confirm"),
    path(
        "auth/password-reset/<str:uidb64>/<str:token>/validate/",
        PasswordResetValidateView.as_view(),
        name="auth-password-reset-validate"),
    path(
        "auth/teacher-invitation/<str:uidb64>/<str:token>/",
        TeacherInvitationConfirmView.as_view(),
        name="auth-teacher-invitation-confirm"),
    path(
        "auth/teacher-invitation/<str:uidb64>/<str:token>/validate/",
        TeacherInvitationValidateView.as_view(),
        name="auth-teacher-invitation-validate"),
    path(
        "auth/teacher-invitation/resend/",
        TeacherInvitationResendView.as_view(),
        name="auth-teacher-invitation-resend"),
]
