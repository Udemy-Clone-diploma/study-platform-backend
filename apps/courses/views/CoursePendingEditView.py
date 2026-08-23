from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import PendingEditLockedError
from apps.courses.models import Course, CoursePendingEdit
from apps.courses.serializers import CoursePendingEditReadSerializer
from apps.courses.services.pending_edit_service import PendingEditService
from apps.courses.views._course_scoped import (
    _get_dict,
    _moderator_profile,
    ensure_can_modify_course,
    get_course_for_request,
)
from apps.users.permissions import IsAdminOrModerator, IsTeacherOrAdmin


def _get_published_course(view, slug: str) -> Course:
    """Resolve a published (or hidden) course the requester owns."""
    course = get_course_for_request(view, slug)
    ensure_can_modify_course(view.request.user, course)
    if course.status not in (Course.StatusChoices.PUBLISHED, Course.StatusChoices.HIDDEN):
        raise PermissionDenied("Pending edits are only allowed on published or hidden courses.")
    return course


def _get_published_course_read(view, slug: str) -> Course:
    """Resolve a published (or hidden) course for read-only access (owner OR moderator/admin)."""
    course = get_course_for_request(view, slug)
    user = view.request.user
    if user.role not in ("administrator", "moderator"):
        ensure_can_modify_course(user, course)
    if course.status not in (Course.StatusChoices.PUBLISHED, Course.StatusChoices.HIDDEN):
        raise PermissionDenied("Pending edits are only allowed on published or hidden courses.")
    return course


def _get_pending_edit(course: Course) -> CoursePendingEdit:
    try:
        return course.pending_edit
    except CoursePendingEdit.DoesNotExist as exc:
        raise NotFound("No pending edit found for this course.") from exc


@extend_schema(tags=["Course Pending Edit"])
class CoursePendingEditView(APIView):
    """
    GET  /courses/{slug}/pending-edit/: read (or auto-create) the pending edit;
         resolves to a hidden draft_course whose slug the teacher edits directly
         via the normal course/module/lesson/etc. CRUD endpoints.
    DELETE /courses/{slug}/pending-edit/: discard all changes (course stays published).
    """

    permission_classes = [IsTeacherOrAdmin]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get(self, request, slug):
        course = _get_published_course_read(self, slug)
        if request.user.role in ("administrator", "moderator"):
            pending_edit = _get_pending_edit(course)
        else:
            pending_edit = PendingEditService.get_or_create(course)
        data = CoursePendingEditReadSerializer(pending_edit, context={"request": request}).data
        return Response(data)

    def delete(self, request, slug):
        course = _get_published_course(self, slug)
        pending_edit = _get_pending_edit(course)
        PendingEditService.discard(pending_edit)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Course Pending Edit"])
class CoursePendingEditSubmitView(APIView):
    """POST /courses/{slug}/pending-edit/submit/: submit for moderation."""

    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, slug):
        course = _get_published_course(self, slug)
        pending_edit = _get_pending_edit(course)

        try:
            updated = PendingEditService.submit(pending_edit)
        except PendingEditLockedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(CoursePendingEditReadSerializer(updated, context={"request": request}).data)


@extend_schema(tags=["Course Pending Edit"])
class CoursePendingEditWithdrawView(APIView):
    """POST /courses/{slug}/pending-edit/withdraw/: pull back from moderation (edits kept)."""

    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, slug):
        course = _get_published_course(self, slug)
        pending_edit = _get_pending_edit(course)

        try:
            updated = PendingEditService.withdraw(pending_edit)
        except PendingEditLockedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(CoursePendingEditReadSerializer(updated, context={"request": request}).data)


@extend_schema(tags=["Course Pending Edit"])
class CoursePendingEditApproveView(APIView):
    """POST /courses/{slug}/pending-edit/approve/: apply changes to live course (moderator only)."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        pending_edit = _get_pending_edit(course)
        PendingEditService.approve(pending_edit, moderator_profile=_moderator_profile(request.user))
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Course Pending Edit"])
class CoursePendingEditRejectView(APIView):
    """POST /courses/{slug}/pending-edit/reject/: return for revision with optional comment."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        pending_edit = _get_pending_edit(course)

        updated = PendingEditService.reject(
            pending_edit,
            moderator_profile=_moderator_profile(request.user),
            basics_field_statuses=_get_dict(request.data, "basics_field_statuses"),
            basics_action=request.data.get("basics_action", ""),
            basics_comment=request.data.get("basics_comment", ""),
            content_item_statuses=_get_dict(request.data, "content_item_statuses"),
            content_action=request.data.get("content_action", ""),
            content_comment=request.data.get("content_comment", ""),
            final_action=request.data.get("final_action", ""),
            final_comment=request.data.get("final_comment", ""),
        )
        return Response(CoursePendingEditReadSerializer(updated, context={"request": request}).data)
