from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.enrollments.models import CourseCompletion
from apps.enrollments.serializers import CourseCompletionSerializer
from apps.users.permissions import IsStudent


@extend_schema(
    tags=["Courses"],
    summary="List completed courses for the current student",
    description="Returns CourseCompletion records (snapshot data) for the authenticated student, newest first.",
)
class StudentCompletionsView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = CourseCompletionSerializer

    def get_queryset(self):
        return CourseCompletion.objects.filter(
            student_profile=self.request.user.student_profile
        )
