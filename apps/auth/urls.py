from django.urls import path

from apps.auth.views import LoginView, MeProfileView, MeView, RegisterView, TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/profile/", MeProfileView.as_view(), name="auth-me-profile"),
]
