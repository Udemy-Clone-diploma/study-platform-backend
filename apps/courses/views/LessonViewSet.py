from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, Lesson, Module
from apps.courses.serializers import LessonSerializer
from apps.courses.serializers.LessonCreateUpdateSerializer import LessonCreateUpdateSerializer
from apps.courses.services import LessonService
from apps.users.models import User


@extend_schema(tags=["Lessons"])
class LessonViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_owned_module(self, request):
        course = get_object_or_404(Course, slug=self.kwargs["course_slug"])
        user = request.user
        is_privileged = user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR)
        if not is_privileged and course.teacher_profile.user_id != user.id:
            raise PermissionDenied()
        return get_object_or_404(Module, pk=self.kwargs["module_pk"], course=course)

    def create(self, request, *args, **kwargs):
        module = self._get_owned_module(request)
        serializer = LessonCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lesson = LessonService.create_lesson(module, serializer.validated_data)
        return Response(LessonSerializer(lesson, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        module = self._get_owned_module(request)
        lesson = get_object_or_404(Lesson, pk=self.kwargs["pk"], module=module)
        serializer = LessonCreateUpdateSerializer(lesson, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        lesson = serializer.save()
        return Response(LessonSerializer(lesson, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        module = self._get_owned_module(request)
        lesson = get_object_or_404(Lesson, pk=self.kwargs["pk"], module=module)
        LessonService.soft_delete_lesson(lesson)
        return Response(status=status.HTTP_204_NO_CONTENT)
