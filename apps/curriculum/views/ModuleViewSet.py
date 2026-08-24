from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import Module
from apps.curriculum.serializers import ModuleCreateUpdateSerializer, ModuleSerializer
from apps.curriculum.services import ModuleService


@extend_schema(tags=["Modules"])
class ModuleViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        serializer = ModuleCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        module = ModuleService.create_module(course, serializer.validated_data)
        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        module = get_object_or_404(Module, pk=kwargs["pk"], course=course)
        serializer = ModuleCreateUpdateSerializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        module = serializer.save()
        return Response(ModuleSerializer(module).data)

    def destroy(self, request, *args, **kwargs):
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        module = get_object_or_404(Module, pk=kwargs["pk"], course=course)
        ModuleService.soft_delete_module(module)
        return Response(status=status.HTTP_204_NO_CONTENT)
