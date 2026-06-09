from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.courses.serializers import CourseListSerializer
from apps.courses.services import CourseService
from apps.users.permissions import IsAdminOrModerator


@extend_schema(
    tags=["Courses"],
    summary="Courses awaiting moderation (no moderator assigned)",
    description="Returns all courses in 'review' status that have no moderator assigned yet.",
)
class UnassignedModerationCoursesView(generics.ListAPIView):
    permission_classes = [IsAdminOrModerator]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        return CourseService.get_unassigned_moderation_queryset()


@extend_schema(
    tags=["Courses"],
    summary="Courses assigned to the current moderator",
    description="Returns all courses assigned to the authenticated moderator, across all statuses.",
)
class MyModerationCoursesView(generics.ListAPIView):
    permission_classes = [IsAdminOrModerator]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        moderator_profile = getattr(self.request.user, "moderator_profile", None)
        if moderator_profile is None:
            return CourseService.annotate_min_price(
                __import__("apps.courses.models", fromlist=["Course"]).Course.objects.none()
            )
        return CourseService.get_my_moderation_queryset(moderator_profile)
