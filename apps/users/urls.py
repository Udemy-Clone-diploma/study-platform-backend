from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.users.views import (
    LoginView,
    MeProfileView,
    MeView,
    RegisterView,
    TokenRefreshView,
    UserViewSet,
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
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/me/profile/", MeProfileView.as_view(), name="auth-me-profile"),
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
