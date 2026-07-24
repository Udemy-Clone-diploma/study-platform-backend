from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.users.filters import UserReportFilter
from apps.users.permissions import IsModerator
from apps.users.serializers import UserReportSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportMineListView(ListAPIView):
    serializer_class = UserReportSerializer
    permission_classes = [IsModerator]
    filterset_class = UserReportFilter

    def get_queryset(self):
        return UserReportService.get_mine_queryset(self.request.user)
