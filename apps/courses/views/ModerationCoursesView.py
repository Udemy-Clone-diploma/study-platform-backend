from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.courses.models import Course
from apps.courses.serializers import CourseListSerializer, RejectedCourseSerializer
from apps.courses.services import CourseService
from apps.courses.views._course_scoped import _moderator_profile
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
        mod = _moderator_profile(self.request.user)
        if mod is None:
            return CourseService.annotate_min_price(Course.objects.none())
        return CourseService.get_my_moderation_queryset(mod)


@extend_schema(
    tags=["Courses"],
    summary="Rejected courses assigned to the current moderator",
)
class MyRejectedModerationCoursesView(generics.ListAPIView):
    permission_classes = [IsAdminOrModerator]
    serializer_class = RejectedCourseSerializer

    def get_queryset(self):
        mod = _moderator_profile(self.request.user)
        if mod is None:
            return CourseService.annotate_min_price(Course.objects.none())
        return CourseService.get_rejected_moderation_queryset(mod)
