from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.users.exceptions import (
    AccountForbiddenError,
    AuthenticationError,
    EmailNotVerifiedError,
    InvalidTokenError,
    ProfileNotAvailableError,
)
from apps.users.messages import EmailMessages
from apps.users.serializers import (
    EmailRequestSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    RefreshTokenSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services.auth_service import AuthService
from apps.users.services.user_service import UserService


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuthService.register(user)
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tokens = AuthService.login(**serializer.validated_data)
        except AuthenticationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except (EmailNotVerifiedError, AccountForbiddenError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.logout(serializer.validated_data["refresh"])
        except (TokenError, InvalidTokenError):
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
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            access_token = AuthService.refresh_access_token(
                serializer.validated_data["refresh"]
            )
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except (InvalidTokenError, AccountForbiddenError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"access": access_token}, status=status.HTTP_200_OK)


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
        try:
            user = UserService.update_profile(request.user, request.data)
        except ProfileNotAvailableError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            return Response(
                {"detail": EmailMessages.INVALID_LINK},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": EmailMessages.CONFIRMED_SUCCESS},
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailVerificationThrottle]

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.resend_verification_email(serializer.validated_data["email"])
        return Response(
            {"detail": EmailMessages.RESEND_SUCCESS},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.request_password_reset(serializer.validated_data["email"])
        return Response(
            {"detail": EmailMessages.PASSWORD_RESET_SENT},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.confirm_password_reset(
                uidb64,
                token,
                serializer.validated_data["password"],
            )
        except InvalidTokenError:
            return Response(
                {"detail": EmailMessages.PASSWORD_RESET_INVALID},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": EmailMessages.PASSWORD_RESET_SUCCESS},
            status=status.HTTP_200_OK,
        )


class PasswordResetValidateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            AuthService.validate_password_reset_token(uidb64, token)
        except InvalidTokenError:
            return Response(
                {"valid": False, "detail": EmailMessages.PASSWORD_RESET_INVALID},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)
