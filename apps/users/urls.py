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
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/me/profile/", MeProfileView.as_view(), name="auth-me-profile"),
    path("", include(router.urls)),
    path("auth/verify-email/<str:uidb64>/<str:token>/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-verification/", ResendVerificationEmailView.as_view(), name="auth-resend-verification"),
]
