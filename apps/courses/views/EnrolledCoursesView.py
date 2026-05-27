from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.courses.serializers import CourseListSerializer
from apps.courses.services import CourseService
from apps.users.permissions import IsStudent


@extend_schema(
    tags=["Courses"],
    summary="List courses the current student is enrolled in",
    description="Returns all non-deleted courses the authenticated student has active access to.",
)
class EnrolledCoursesView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        return CourseService.get_enrolled_courses_queryset(self.request.user.student_profile)
