from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import Module, Question, Test
from apps.curriculum.serializers import QuestionCreateUpdateSerializer, QuestionSerializer
from apps.curriculum.services import QuestionService


@extend_schema(tags=["Tests"])
class QuestionViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_test(self, request, kwargs) -> Test:
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        module = get_object_or_404(Module, pk=kwargs["module_pk"], course=course)
        return get_object_or_404(Test, pk=kwargs["test_pk"], module=module)

    def create(self, request, *args, **kwargs):
        test = self._get_test(request, kwargs)
        serializer = QuestionCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = QuestionService.create_question(test, serializer.validated_data)
        return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        test = self._get_test(request, kwargs)
        question = get_object_or_404(Question, pk=kwargs["pk"], test=test)
        serializer = QuestionCreateUpdateSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(QuestionSerializer(question).data)

    def destroy(self, request, *args, **kwargs):
        test = self._get_test(request, kwargs)
        question = get_object_or_404(Question, pk=kwargs["pk"], test=test)
        QuestionService.soft_delete_question(question)
        return Response(status=status.HTTP_204_NO_CONTENT)
