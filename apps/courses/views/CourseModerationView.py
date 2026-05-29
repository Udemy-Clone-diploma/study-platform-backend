from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import CoursesError
from apps.courses.serializers import CourseDetailSerializer
from apps.courses.services.course_service import CourseService
from apps.courses.views._course_scoped import get_course_for_request
from apps.users.permissions import IsAdminOrModerator


@extend_schema(tags=["Courses"])
class CourseApproveView(APIView):
    """POST /courses/{slug}/approve/ — publish a course that is awaiting review."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        try:
            moderator_profile = getattr(request.user, "moderator_profile", None)
            course = CourseService.approve_course(course, moderator_profile)
        except CoursesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            CourseService.serialize_course_detail(course, context=self.get_serializer_context()),
        )

    def get_serializer_context(self):
        return {"request": self.request}


@extend_schema(tags=["Courses"])
class CourseRejectView(APIView):
    """POST /courses/{slug}/reject/ — return a course for revision with an optional comment."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        comment = request.data.get("comment", "")
        try:
            moderator_profile = getattr(request.user, "moderator_profile", None)
            course = CourseService.reject_course(course, moderator_profile, comment=comment)
        except CoursesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            CourseService.serialize_course_detail(course, context=self.get_serializer_context()),
        )

    def get_serializer_context(self):
        return {"request": self.request}