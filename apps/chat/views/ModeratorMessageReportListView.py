from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.chat.models import MessageReport
from apps.chat.serializers import MessageReportSerializer


@extend_schema(tags=["Chat"])
class ModeratorMessageReportListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageReportSerializer

    def get_queryset(self):
        if self.request.user.role != "moderator":
            raise PermissionDenied("Only moderators can view message reports.")
        return MessageReport.objects.select_related(
            "reporter",
            "message",
            "message__sender",
            "message__chat",
        ).prefetch_related("message__attachments")
