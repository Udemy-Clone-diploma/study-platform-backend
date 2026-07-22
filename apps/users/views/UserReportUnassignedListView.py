from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.users.filters import UserReportFilter
from apps.users.permissions import IsAdminOrModerator
from apps.users.serializers import UserReportSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportUnassignedListView(ListAPIView):
    serializer_class = UserReportSerializer
    permission_classes = [IsAdminOrModerator]
    filterset_class = UserReportFilter

    def get_queryset(self):
        return UserReportService.get_unassigned_queryset(self.request.user)
