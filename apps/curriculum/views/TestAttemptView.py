from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.pagination import StandardResultsSetPagination
from apps.courses.views._course_scoped import get_course_for_request
from apps.curriculum.exceptions import RetakeNotAllowedError, TestNotAttemptableError
from apps.curriculum.models import Test, TestAttempt
from apps.curriculum.serializers import (
    AttemptSubmitSerializer,
    TestAttemptListSerializer,
    TestAttemptResultSerializer,
)
from apps.curriculum.services import TestAttemptService
from apps.enrollments.services import EnrollmentService
from apps.users.models import StudentProfile, User


@extend_schema(tags=["Tests"])
class TestAttemptView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    serializer_class = TestAttemptListSerializer

    @extend_schema(responses=TestAttemptListSerializer(many=True))
    def get(self, request, slug: str, test_id: int):
        test, student_profile = self._resolve(request, slug, test_id)
        attempts = TestAttempt.objects.filter(
            student_profile=student_profile, test=test,
        )
        page = self.paginate_queryset(attempts)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(request=AttemptSubmitSerializer, responses=TestAttemptResultSerializer)
    def post(self, request, slug: str, test_id: int):
        test, student_profile = self._resolve(request, slug, test_id)
        serializer = AttemptSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = TestAttemptService.submit(
                student_profile, test, serializer.validated_data["answers"],
            )
        except TestNotAttemptableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except RetakeNotAllowedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(result, status=status.HTTP_201_CREATED)

    def _resolve(self, request, slug: str, test_id: int) -> tuple[Test, StudentProfile]:
        course = get_course_for_request(self, slug)
        test = Test.objects.filter(pk=test_id, module__course=course).first()
        if test is None:
            raise NotFound("Test not found.")
        student_profile = self._enrolled_student_profile(request.user, course)
        if student_profile is None:
            raise PermissionDenied(
                "You must be enrolled in this course to take its tests."
            )
        return test, student_profile

    @staticmethod
    def _enrolled_student_profile(user, course) -> StudentProfile | None:
        if user.role != User.RoleChoices.STUDENT:
            return None
        try:
            student_profile = user.student_profile
        except StudentProfile.DoesNotExist:
            return None
        if EnrollmentService.student_has_course_access(student_profile, course):
            return student_profile
        return None
