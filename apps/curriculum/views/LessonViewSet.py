from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import Lesson, Module
from apps.curriculum.serializers import LessonCreateUpdateSerializer, LessonSerializer
from apps.curriculum.services import LessonService


@extend_schema(tags=["Lessons"])
class LessonViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_module(self, request, kwargs) -> Module:
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        return get_object_or_404(Module, pk=kwargs["module_pk"], course=course)

    def create(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        serializer = LessonCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lesson = LessonService.create_lesson(module, serializer.validated_data)
        return Response(
            LessonSerializer(lesson, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        lesson = get_object_or_404(Lesson, pk=kwargs["pk"], module=module)
        serializer = LessonCreateUpdateSerializer(lesson, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        lesson = serializer.save()
        return Response(LessonSerializer(lesson, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        lesson = get_object_or_404(Lesson, pk=kwargs["pk"], module=module)
        LessonService.soft_delete_lesson(lesson)
        return Response(status=status.HTTP_204_NO_CONTENT)
