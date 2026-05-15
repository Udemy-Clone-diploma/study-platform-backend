from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, Module
from apps.courses.serializers import ModuleSerializer
from apps.courses.serializers.ModuleCreateUpdateSerializer import ModuleCreateUpdateSerializer
from apps.users.models import User


@extend_schema(tags=["Modules"])
class ModuleViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_owned_course(self, request):
        course = get_object_or_404(Course, slug=self.kwargs["course_slug"])
        user = request.user
        is_privileged = user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR)
        if not is_privileged and course.teacher_profile.user_id != user.id:
            raise PermissionDenied()
        return course

    def create(self, request, *args, **kwargs):
        course = self._get_owned_course(request)
        serializer = ModuleCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = Module.objects.filter(course=course).count() + 1
        module = serializer.save(course=course, order=order)
        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        course = self._get_owned_course(request)
        module = get_object_or_404(Module, pk=self.kwargs["pk"], course=course)
        serializer = ModuleCreateUpdateSerializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        module = serializer.save()
        return Response(ModuleSerializer(module).data)

    def destroy(self, request, *args, **kwargs):
        course = self._get_owned_course(request)
        module = get_object_or_404(Module, pk=self.kwargs["pk"], course=course)
        module.is_deleted = True
        module.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
