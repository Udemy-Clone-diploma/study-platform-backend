from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import Module, Test
from apps.curriculum.serializers import TestCreateUpdateSerializer, TestSerializer
from apps.curriculum.services import TestService


@extend_schema(tags=["Tests"])
class TestViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_module(self, request, kwargs) -> Module:
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        return get_object_or_404(Module, pk=kwargs["module_pk"], course=course)

    def create(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        serializer = TestCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test = TestService.create_test(module, serializer.validated_data)
        return Response(TestSerializer(test).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        test = get_object_or_404(Test, pk=kwargs["pk"], module=module)
        serializer = TestCreateUpdateSerializer(test, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        test = serializer.save()
        return Response(TestSerializer(test).data)

    def destroy(self, request, *args, **kwargs):
        module = self._get_module(request, kwargs)
        test = get_object_or_404(Test, pk=kwargs["pk"], module=module)
        TestService.soft_delete_test(test)
        return Response(status=status.HTTP_204_NO_CONTENT)
