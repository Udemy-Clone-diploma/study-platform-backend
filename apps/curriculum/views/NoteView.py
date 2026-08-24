from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import get_course_for_request
from apps.curriculum.models import Lesson
from apps.curriculum.serializers import NoteSerializer
from apps.curriculum.services import NoteService
from apps.enrollments.services import EnrollmentService


@extend_schema(tags=["Lessons"])
class NoteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NoteSerializer

    @extend_schema(responses=NoteSerializer)
    def get(self, request, slug: str, lesson_id: int):
        lesson = self._resolve_lesson(slug, lesson_id)
        note = NoteService.get_note(request.user, lesson)
        if note is None:
            return Response(
                {"detail": "Note not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(NoteSerializer(note).data)

    @extend_schema(request=NoteSerializer, responses=NoteSerializer)
    def put(self, request, slug: str, lesson_id: int):
        lesson = self._resolve_lesson(slug, lesson_id)
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = NoteService.upsert_note(
            request.user,
            lesson,
            serializer.validated_data["content"],
        )
        return Response(NoteSerializer(note).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, slug: str, lesson_id: int):
        lesson = self._resolve_lesson(slug, lesson_id)
        NoteService.delete_note(request.user, lesson)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _resolve_lesson(self, slug: str, lesson_id: int) -> Lesson:
        course = get_course_for_request(self, slug)
        lesson = Lesson.objects.filter(pk=lesson_id, module__course=course).first()
        if lesson is None:
            raise NotFound("Lesson not found.")
        if not EnrollmentService.is_enrolled(self.request.user, course):
            raise PermissionDenied("You must be enrolled in this course to use notes.")
        return lesson
