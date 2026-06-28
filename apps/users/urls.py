from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    ChangePasswordView,
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
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

urlpatterns = [
    path("users/top-teachers/", TopTeachersView.as_view(), name="top-teachers"),
    path("users/search/",       UserSearchView.as_view(),  name="user-search"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
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
]
