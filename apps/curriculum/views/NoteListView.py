from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.curriculum.serializers import NoteListItemSerializer
from apps.curriculum.services import NoteService
from apps.enrollments.models import CourseCompletion


@extend_schema(tags=["Notes"])
class NoteListView(generics.ListAPIView):
    """GET /notes/: every lesson note the current user has written, across all courses."""

    permission_classes = [IsAuthenticated]
    serializer_class = NoteListItemSerializer

    def get_queryset(self):
        return NoteService.list_notes_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        target = page if page is not None else queryset

        completed_course_ids = set(
            CourseCompletion.objects.filter(
                student_profile__user=request.user,
                course_id__in={note.course_id for note in target if note.course_id is not None},
            ).values_list("course_id", flat=True)
        )
        serializer = self.get_serializer(
            target,
            many=True,
            context={**self.get_serializer_context(), "completed_course_ids": completed_course_ids},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
