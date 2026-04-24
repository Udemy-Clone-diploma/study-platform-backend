from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.users.models import User
from apps.users.serializers import (
    PROFILE_MODELS,
    PROFILE_SERIALIZERS,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services.auth_service import (
    AccountForbiddenError,
    AuthenticationError,
    AuthService,
    EmailNotVerifiedError,
    InvalidTokenError,
)
from apps.users.services.email_messages_service import EmailMessages
from apps.users.services.send_email_service import send_verification_email


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        return Response(
            {"detail": "Registration successful. Check your email for confirmation"},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = AuthService.login(email, password)
        except AuthenticationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except EmailNotVerifiedError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except AccountForbiddenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            AuthService.logout(refresh_token)
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_205_RESET_CONTENT,
        )


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            access = AuthService.refresh_access_token(refresh_token)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except (User.DoesNotExist, KeyError):
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
        except AccountForbiddenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"access": access}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class MeProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer_class = PROFILE_SERIALIZERS.get(user.role)
        profile_model = PROFILE_MODELS.get(user.role)

        if not serializer_class or not profile_model:
            return Response(
                {"detail": "Profile is not available for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = profile_model.objects.get_or_create(user=user)
        serializer = serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user).data)


class EmailVerificationThrottle(AnonRateThrottle):
    rate = "5/hour"


class PasswordResetThrottle(AnonRateThrottle):
    rate = "5/hour"


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            AuthService.verify_email(uidb64, token)
        except InvalidTokenError:
            return Response({"detail": EmailMessages.INVALID_LINK}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": EmailMessages.CONFIRMED_SUCCESS}, status=status.HTTP_200_OK)


class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailVerificationThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"detail": EmailMessages.EMAIL_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuthService.resend_verification_email(email)
        return Response({"detail": EmailMessages.RESEND_SUCCESS}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        AuthService.request_password_reset(email)
        return Response(
            {"detail": "If the account exists, a password reset email has been sent"},
            status=status.HTTP_200_OK,
        )


class PasswordResetValidateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            AuthService.validate_password_reset_token(uidb64, token)
        except InvalidTokenError:
            return Response(
                {"valid": False, "detail": "Invalid or expired password reset link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        password = request.data.get("password")
        if not password or len(password) < 8:
            return Response(
                {"detail": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            AuthService.confirm_password_reset(uidb64, token, password)
        except InvalidTokenError:
            return Response(
                {"detail": "Invalid or expired password reset link"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Password has been successfully changed"},
            status=status.HTTP_200_OK,
        )

