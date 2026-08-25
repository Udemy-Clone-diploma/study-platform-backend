from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.users.filters import UserReportFilter
from apps.users.models import UserReport
from apps.users.permissions import IsAdmin
from apps.users.serializers import UserReportSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportEscalatedListView(ListAPIView):
    serializer_class = UserReportSerializer
    permission_classes = [IsAdmin]
    filterset_class = UserReportFilter

    def get_queryset(self):
        # drf-spectacular introspects with AnonymousUser; without this the filterset is dropped.
        if getattr(self, "swagger_fake_view", False):
            return UserReport.objects.none()
        queryset = UserReportService.get_escalated_queryset(self.request.user)
        if "status" not in self.request.query_params:
            queryset = queryset.filter(status=UserReport.StatusChoices.ESCALATED)
        return queryset
