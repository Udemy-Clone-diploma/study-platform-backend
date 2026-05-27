from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, Module, Question, Test
from apps.courses.serializers import QuestionSerializer, QuestionCreateUpdateSerializer
from apps.courses.services import QuestionService
from apps.users.models import User


@extend_schema(tags=["Tests"])
class QuestionViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_owned_test(self, request):
        course = get_object_or_404(Course, slug=self.kwargs["course_slug"])
        user = request.user
        is_privileged = user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR)
        if not is_privileged and course.teacher_profile.user_id != user.id:
            raise PermissionDenied()
        module = get_object_or_404(Module, pk=self.kwargs["module_pk"], course=course)
        return get_object_or_404(Test, pk=self.kwargs["test_pk"], module=module)

    def create(self, request, *args, **kwargs):
        test = self._get_owned_test(request)
        serializer = QuestionCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = QuestionService.create_question(test, serializer.validated_data)
        return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        test = self._get_owned_test(request)
        question = get_object_or_404(Question, pk=self.kwargs["pk"], test=test)
        serializer = QuestionCreateUpdateSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(QuestionSerializer(question).data)

    def destroy(self, request, *args, **kwargs):
        test = self._get_owned_test(request)
        question = get_object_or_404(Question, pk=self.kwargs["pk"], test=test)
        QuestionService.soft_delete_question(question)
        return Response(status=status.HTTP_204_NO_CONTENT)
