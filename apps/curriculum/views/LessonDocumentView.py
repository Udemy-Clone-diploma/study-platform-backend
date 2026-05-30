import re

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import Lesson, LessonDocument, Module
from apps.curriculum.serializers import LessonDocumentSerializer


def _unique_name(lesson: Lesson, original_name: str) -> str:
    existing = set(lesson.documents.values_list("original_name", flat=True))
    if original_name not in existing:
        return original_name
    stem, _, ext = original_name.rpartition(".")
    ext = f".{ext}" if ext else ""
    stem = stem or original_name
    i = 1
    while True:
        candidate = f"{stem} ({i}){ext}"
        if candidate not in existing:
            return candidate
        i += 1


@extend_schema(tags=["Lessons"])
class LessonDocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_lesson(self, request, kwargs) -> Lesson:
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        module = get_object_or_404(Module, pk=kwargs["module_pk"], course=course)
        return get_object_or_404(Lesson, pk=kwargs["lesson_pk"], module=module)

    def post(self, request, *args, **kwargs):
        lesson = self._get_lesson(request, kwargs)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        original_name = _unique_name(lesson, file.name)
        doc = LessonDocument.objects.create(lesson=lesson, file=file, original_name=original_name)
        return Response(
            LessonDocumentSerializer(doc, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Lessons"])
class LessonDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        doc = get_object_or_404(LessonDocument, pk=kwargs["doc_pk"])
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
