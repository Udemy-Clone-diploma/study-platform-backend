from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.common.serializers import AccessTokenSerializer, MessageSerializer, TokenPairSerializer
from apps.users.exceptions import (
    AccountForbiddenError,
    AuthenticationError,
    EmailNotVerifiedError,
    InvalidTokenError,
    ProfileNotAvailableError,
)
from apps.users.messages import EmailMessages
from apps.users.models import User
from apps.users.serializers import (
    ChangePasswordSerializer,
    EmailRequestSerializer,
    LoginSerializer,
    ModeratorProfileSerializer,
    PasswordResetConfirmSerializer,
    RefreshTokenSerializer,
    StudentProfileSerializer,
    TeacherProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services.auth_service import AuthService
from apps.users.services.user_service import UserService


@extend_schema(tags=["Auth"])
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=UserRegistrationSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuthService.register(user)
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Auth"])
class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: TokenPairSerializer, 401: MessageSerializer, 403: MessageSerializer},
    )
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


@extend_schema(tags=["Auth"])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RefreshTokenSerializer,
        responses={205: MessageSerializer, 400: MessageSerializer},
    )
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


@extend_schema(tags=["Auth"])
class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RefreshTokenSerializer,
        responses={200: AccessTokenSerializer, 401: MessageSerializer},
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tokens = AuthService.refresh_access_token(
                serializer.validated_data["refresh"]
            )
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except (InvalidTokenError, AccountForbiddenError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(tokens, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)

    @extend_schema(request=UserUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user, context={"request": request}).data)


@extend_schema(tags=["Auth"])
class TeacherProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TeacherProfileSerializer

    @extend_schema(responses={200: UserSerializer, 400: MessageSerializer})
    def patch(self, request):
        if request.user.role != User.RoleChoices.TEACHER:
            return Response({"detail": "Not available for your role."}, status=status.HTTP_403_FORBIDDEN)
        user = UserService.update_profile(request.user, request.data)
        return Response(UserSerializer(user, context={"request": request}).data)


@extend_schema(tags=["Auth"])
class StudentProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentProfileSerializer

    @extend_schema(responses={200: UserSerializer, 400: MessageSerializer})
    def patch(self, request):
        if request.user.role != User.RoleChoices.STUDENT:
            return Response({"detail": "Not available for your role."}, status=status.HTTP_403_FORBIDDEN)
        user = UserService.update_profile(request.user, request.data)
        return Response(UserSerializer(user, context={"request": request}).data)


@extend_schema(tags=["Auth"])
class ModeratorProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ModeratorProfileSerializer

    @extend_schema(responses={200: UserSerializer, 400: MessageSerializer})
    def patch(self, request):
        if request.user.role != User.RoleChoices.MODERATOR:
            return Response({"detail": "Not available for your role."}, status=status.HTTP_403_FORBIDDEN)
        user = UserService.update_profile(request.user, request.data)
        return Response(UserSerializer(user, context={"request": request}).data)


@extend_schema(tags=["Auth"])
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: MessageSerializer, 400: MessageSerializer})
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


@extend_schema(tags=["Auth"])
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    @extend_schema(request=EmailRequestSerializer, responses={200: MessageSerializer})
    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.resend_verification_email(serializer.validated_data["email"])
        return Response(
            {"detail": EmailMessages.RESEND_SUCCESS},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        operation_id="auth_password_reset_request",
        request=EmailRequestSerializer,
        responses={200: MessageSerializer},
    )
    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.request_password_reset(serializer.validated_data["email"])
        return Response(
            {"detail": EmailMessages.PASSWORD_RESET_SENT},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_password_reset_confirm",
        request=PasswordResetConfirmSerializer,
        responses={200: MessageSerializer, 400: MessageSerializer},
    )
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


@extend_schema(tags=["Auth"])
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: MessageSerializer, 400: MessageSerializer})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Incorrect current password."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class PasswordResetValidateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer("TokenValidOkSerializer", {"valid": drf_serializers.BooleanField()}),
            400: inline_serializer(
                "TokenValidErrorSerializer",
                {"valid": drf_serializers.BooleanField(), "detail": drf_serializers.CharField()},
            ),
        }
    )
    def get(self, request, uidb64, token):
        try:
            AuthService.validate_password_reset_token(uidb64, token)
        except InvalidTokenError:
            return Response(
                {"valid": False, "detail": EmailMessages.PASSWORD_RESET_INVALID},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class TeacherInvitationValidateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer("TeacherInvitationValidOkSerializer", {"valid": drf_serializers.BooleanField()}),
            400: inline_serializer(
                "TeacherInvitationValidErrorSerializer",
                {"valid": drf_serializers.BooleanField(), "detail": drf_serializers.CharField()},
            ),
        }
    )
    def get(self, request, uidb64, token):
        try:
            AuthService.validate_teacher_invitation_token(uidb64, token)
        except InvalidTokenError:
            return Response(
                {"valid": False, "detail": EmailMessages.TEACHER_INVITATION_INVALID},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth"])
class TeacherInvitationResendView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_invitation_resend"

    @extend_schema(request=EmailRequestSerializer, responses={200: MessageSerializer})
    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.resend_teacher_invitation_email(serializer.validated_data["email"])
        return Response(
            {"detail": EmailMessages.TEACHER_INVITATION_RESEND_SUCCESS},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class TeacherInvitationConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="auth_teacher_invitation_confirm",
        request=PasswordResetConfirmSerializer,
        responses={200: MessageSerializer, 400: MessageSerializer},
    )
    def post(self, request, uidb64, token):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AuthService.confirm_teacher_invitation(
                uidb64,
                token,
                serializer.validated_data["password"],
            )
        except InvalidTokenError:
            return Response(
                {"detail": EmailMessages.TEACHER_INVITATION_INVALID},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": EmailMessages.TEACHER_INVITATION_SUCCESS},
            status=status.HTTP_200_OK,
        )
