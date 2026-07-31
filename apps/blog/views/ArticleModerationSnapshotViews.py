from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from apps.blog.models import ArticleModerationSnapshot
from apps.blog.serializers import ArticleModerationSnapshotSerializer
from apps.users.permissions import IsAdminOrModerator


@extend_schema(tags=["Blog"])
class ArticleModerationSnapshotListView(ListAPIView):
    """GET /blog/moderation-snapshots/?decision=<rejected|published>

    Permanent history of reject/approve decisions across the shared moderation
    queue -- independent of the live Article's current status (see
    ArticleService._create_snapshot). Shared across all moderators, same as the
    rest of the "On Review" queue.
    """

    serializer_class = ArticleModerationSnapshotSerializer
    permission_classes = [IsAdminOrModerator]
    pagination_class = None

    def get_queryset(self):
        qs = ArticleModerationSnapshot.objects.select_related(
            "article", "moderator_profile__user",
        ).order_by("-created_at")
        decision = self.request.query_params.get("decision")
        if decision:
            qs = qs.filter(decision=decision)
        return qs
