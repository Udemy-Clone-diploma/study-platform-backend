from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import CoursesError
from apps.courses.services.course_service import CourseService
from apps.courses.views._course_scoped import _get_dict, _moderator_profile, get_course_for_request
from apps.users.permissions import IsAdminOrModerator


@extend_schema(tags=["Courses"])
class SaveReviewDraftView(APIView):
    """POST /courses/{slug}/save-review-draft/: persist moderator review progress without changing course status."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        CourseService.save_review_draft(
            course,
            _moderator_profile(request.user),
            basics_field_statuses=_get_dict(request.data, "basics_field_statuses"),
            basics_action=request.data.get("basics_action", ""),
            basics_comment=request.data.get("basics_comment", ""),
            content_item_statuses=_get_dict(request.data, "content_item_statuses"),
            content_action=request.data.get("content_action", ""),
            content_comment=request.data.get("content_comment", ""),
            final_action=request.data.get("final_action", ""),
            final_comment=request.data.get("final_comment", ""),
        )
        return Response({"detail": "Draft saved."}, status=status.HTTP_200_OK)


@extend_schema(tags=["Courses"])
class CourseApproveView(APIView):
    """POST /courses/{slug}/approve/: publish a course that is awaiting review."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        try:
            course = CourseService.approve_course(course, _moderator_profile(request.user))
        except CoursesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            CourseService.serialize_course_detail(course, context={"request": request}),
        )


@extend_schema(tags=["Courses"])
class CourseAssignModeratorView(APIView):
    """POST /courses/{slug}/assign-moderator/: assign the current moderator to a course."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        try:
            CourseService.assign_moderator_self(course, _moderator_profile(request.user))
        except CoursesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        # The frontend discards the response body, so avoid re-serializing the
        # full course tree (with moderator-only image/video hashing) just to
        # throw it away.
        return Response({"detail": "Moderator assigned."})


@extend_schema(tags=["Courses"])
class CourseRejectView(APIView):
    """POST /courses/{slug}/reject/: return a course for revision with an optional comment."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        try:
            course = CourseService.reject_course(
                course,
                _moderator_profile(request.user),
                basics_field_statuses=_get_dict(request.data, "basics_field_statuses"),
                basics_action=request.data.get("basics_action", ""),
                basics_comment=request.data.get("basics_comment", ""),
                content_item_statuses=_get_dict(request.data, "content_item_statuses"),
                content_action=request.data.get("content_action", ""),
                content_comment=request.data.get("content_comment", ""),
                final_action=request.data.get("final_action", ""),
                final_comment=request.data.get("final_comment", ""),
            )
        except CoursesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            CourseService.serialize_course_detail(course, context={"request": request}),
        )
