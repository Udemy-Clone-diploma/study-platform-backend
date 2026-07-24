from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.users.filters import UserReportFilter
from apps.users.permissions import IsAdmin
from apps.users.serializers import UserReportSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportAllListView(ListAPIView):
    serializer_class = UserReportSerializer
    permission_classes = [IsAdmin]
    filterset_class = UserReportFilter

    def get_queryset(self):
        return UserReportService.get_all_queryset()
