from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from apps.users.services.token_generator_service import email_verification_token
from apps.users.services.send_email_service import send_verification_email
from apps.users.services.email_messages_service import EmailMessages
from apps.users.services.tokens import get_tokens_for_user
from rest_framework.throttling import AnonRateThrottle

from apps.users.models import User
from apps.users.serializers import (
    PROFILE_MODELS,
    PROFILE_SERIALIZERS,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


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
            user = User.all_objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        if not user.is_email_verified:
            return Response(
                {"detail": "Please confirm your email before logging in"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_deleted:
            return Response(
                {"detail": "This account has been deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_blocked:
            return Response(
                {"detail": "This account has been blocked."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(get_tokens_for_user(user), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Logged out successfully."},
            status=status.HTTP_205_RESET_CONTENT
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
            token = RefreshToken(refresh_token)
            user_id = token[jwt_settings.USER_ID_CLAIM] # type: ignore
            user = User.all_objects.get(pk=user_id)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except (User.DoesNotExist, KeyError):
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        if user.is_deleted:
            return Response(
                {"detail": "This account has been deleted."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if user.is_blocked:
            return Response(
                {"detail": "This account has been blocked."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = token.access_token
        access["role"] = user.role
        return Response({"access": str(access)}, status=status.HTTP_200_OK)


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



class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.all_objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            return Response({"detail": EmailMessages.INVALID_LINK}, status=400)

        if user.is_deleted or user.is_blocked:
            return Response({"detail": EmailMessages.INVALID_LINK}, status=400)
        

        if not email_verification_token.check_token(user, token):
            return Response({"detail": EmailMessages.INVALID_LINK}, status=400)

        
       
        user.is_email_verified = True
        user.save()

        return Response({"detail": EmailMessages.CONFIRMED_SUCCESS}, status=200)


class EmailVerificationThrottle(AnonRateThrottle):
    rate = "5/hour"
    
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailVerificationThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"detail": EmailMessages.EMAIL_REQUIRED}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.all_objects.get(email=email, is_deleted=False, is_blocked=False)
        except User.DoesNotExist:
            return Response({"detail": EmailMessages.RESEND_SUCCESS}, status=status.HTTP_200_OK)

        if user.is_email_verified:
            return Response({"detail": EmailMessages.RESEND_SUCCESS}, status=status.HTTP_200_OK)

        send_verification_email(user)
        return Response({"detail": EmailMessages.RESEND_SUCCESS}, status=status.HTTP_200_OK)
    