from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.preferences import effective_preferences
from apps.notifications.serializers import NotificationPreferenceUpdateSerializer
from apps.notifications.services import NotificationService


@extend_schema(tags=["Notifications"])
class NotificationPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        overrides = NotificationService.get_overrides(request.user)
        return Response(effective_preferences(overrides))

    @extend_schema(
        request=NotificationPreferenceUpdateSerializer,
        responses=OpenApiTypes.OBJECT,
    )
    def patch(self, request):
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        overrides = NotificationService.update_preferences(
            request.user, serializer.validated_data
        )
        return Response(effective_preferences(overrides))
