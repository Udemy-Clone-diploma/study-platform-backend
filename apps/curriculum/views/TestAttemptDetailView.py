from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import get_course_for_request
from apps.curriculum.models import Test, TestAttempt
from apps.curriculum.serializers import TestAttemptResultSerializer
from apps.curriculum.services import TestAttemptService
from apps.users.models import User


@extend_schema(tags=["Tests"])
class TestAttemptDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TestAttemptResultSerializer

    @extend_schema(responses=TestAttemptResultSerializer)
    def get(self, request, slug: str, test_id: int, attempt_id: int):
        course = get_course_for_request(self, slug)
        test = Test.objects.filter(pk=test_id, module__course=course).first()
        if test is None:
            raise NotFound("Test not found.")
        attempt = (
            TestAttempt.objects.filter(pk=attempt_id, test=test)
            .select_related("student_profile")
            .first()
        )
        if attempt is None:
            raise NotFound("Attempt not found.")
        if not self._can_view(request.user, course, attempt):
            raise PermissionDenied("You do not have access to this attempt.")
        return Response(TestAttemptService.result_for_attempt(attempt))

    @staticmethod
    def _can_view(user, course, attempt: TestAttempt) -> bool:
        if attempt.student_profile.user_id == user.id:
            return True
        if user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR):
            return True
        if user.role == User.RoleChoices.TEACHER:
            return course.teacher_profile.user_id == user.id
        return False
