from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, Module, Test
from apps.courses.serializers import TestSerializer, TestCreateUpdateSerializer
from apps.courses.services import TestService
from apps.users.models import User


@extend_schema(tags=["Tests"])
class TestViewSet(viewsets.GenericViewSet):
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
        serializer = TestCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test = TestService.create_test(module, serializer.validated_data)
        return Response(TestSerializer(test).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        module = self._get_owned_module(request)
        test = get_object_or_404(Test, pk=self.kwargs["pk"], module=module)
        serializer = TestCreateUpdateSerializer(test, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        test = serializer.save()
        return Response(TestSerializer(test).data)

    def destroy(self, request, *args, **kwargs):
        module = self._get_owned_module(request)
        test = get_object_or_404(Test, pk=self.kwargs["pk"], module=module)
        TestService.soft_delete_test(test)
        return Response(status=status.HTTP_204_NO_CONTENT)
