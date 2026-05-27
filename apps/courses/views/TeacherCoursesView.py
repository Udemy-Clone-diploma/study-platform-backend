from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.courses.serializers import CourseListSerializer
from apps.courses.services import CourseService
from apps.users.permissions import IsTeacher


@extend_schema(
    tags=["Courses"],
    summary="List the current teacher's own courses",
    description="Returns all non-deleted courses created by the authenticated teacher, across all statuses.",
)
class TeacherCoursesView(generics.ListAPIView):
    permission_classes = [IsTeacher]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        return CourseService.get_teacher_courses_queryset(self.request.user.teacher_profile)
