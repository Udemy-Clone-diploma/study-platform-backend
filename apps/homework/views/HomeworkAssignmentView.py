from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.homework.models import HomeworkAssignment
from apps.homework.serializers import HomeworkAssignmentSerializer


@extend_schema(tags=["Homework"])
class HomeworkAssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = HomeworkAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def _get_course(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(self.request.user, course)
        return course

    def get_queryset(self):
        return (
            HomeworkAssignment.objects.filter(course=self._get_course())
            .select_related("module", "lesson")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["course"] = self._get_course()
        return context

    def perform_create(self, serializer):
        serializer.save(course=self._get_course(), created_by=self.request.user)
