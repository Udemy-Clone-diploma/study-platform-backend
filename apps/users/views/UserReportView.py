from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.serializers import MessageSerializer
from apps.users.exceptions import CannotReportSelfError, UserAlreadyReportedError
from apps.users.models import User
from apps.users.serializers import UserReportCreateSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["Users"])
class UserReportView(APIView):
    """Submit a complaint about another user's public profile."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "user_report"

    @extend_schema(
        request=UserReportCreateSerializer,
        responses={
            201: MessageSerializer,
            400: MessageSerializer,
            403: MessageSerializer,
            404: MessageSerializer,
            409: MessageSerializer,
            429: MessageSerializer,
        },
    )
    def post(self, request, user_id: int):
        reported_user = get_object_or_404(User, pk=user_id)
        serializer = UserReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            UserReportService.create_report(
                request.user,
                reported_user,
                **serializer.validated_data,
            )
        except CannotReportSelfError:
            return Response(
                {"detail": "You cannot report your own profile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except UserAlreadyReportedError:
            return Response(
                {"detail": "You have already reported this user."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"detail": "Report submitted."},
            status=status.HTTP_201_CREATED,
        )
