from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from apps.users.permissions import IsAdmin, IsModerator
from apps.users.serializers import UserSerializer
from apps.users.services.moderator_statistics_service import (
    ModeratorStatisticsService,
)


def _dashboard_response(request, moderator: User) -> Response:
    data = ModeratorStatisticsService.build(moderator)
    data["moderator"] = UserSerializer(
        moderator,
        context={"request": request},
    ).data
    return Response(data)


@extend_schema(tags=["Users"], summary="Current moderator dashboard statistics")
class ModeratorDashboardView(APIView):
    permission_classes = [IsModerator]

    def get(self, request):
        moderator = get_object_or_404(
            User.objects.select_related("moderator_profile"),
            pk=request.user.pk,
            role=User.RoleChoices.MODERATOR,
            moderator_profile__isnull=False,
        )
        return _dashboard_response(request, moderator)


@extend_schema(tags=["Users"], summary="Admin-only moderator performance profile")
class AdminModeratorDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, user_id: int):
        moderator = get_object_or_404(
            User.all_objects.select_related("moderator_profile"),
            pk=user_id,
            role=User.RoleChoices.MODERATOR,
            moderator_profile__isnull=False,
        )
        return _dashboard_response(request, moderator)
