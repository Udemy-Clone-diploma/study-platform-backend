from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import CoursesError
from apps.courses.models import ApprovedCourseRecord, RejectedCourseRecord
from apps.courses.serializers import (
    ApprovedCourseRecordSerializer,
    RejectedCourseRecordSerializer,
    RejectedCourseSerializer,
)
from apps.courses.services import CourseService
from apps.courses.views._course_scoped import get_course_for_request
from apps.users.permissions import IsAdminOrModerator, IsTeacherOrAdmin


@extend_schema(tags=["Courses"], summary="List rejected courses for the current teacher")
class RejectedCoursesView(generics.ListAPIView):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = RejectedCourseSerializer

    def get_queryset(self):
        return CourseService.get_rejected_courses_queryset(self.request.user.teacher_profile)


@extend_schema(tags=["Courses"], summary="Restore a rejected course to draft for editing")
class CourseRestoreFromRejectedView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        try:
            course = CourseService.restore_rejected_course(course)
        except CoursesError as exc:
            return Response(
                {"detail": str(exc), "current_status": course.status},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            CourseService.serialize_course_detail(course, context={"request": request}),
        )


@extend_schema(tags=["Courses"], summary="Copy a rejected course into a new draft")
class CourseCopyToDraftView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, slug):
        course = get_course_for_request(self, slug)
        if course.status != "rejected":
            return Response(
                {"detail": "Only rejected courses can be copied to draft."},
                status=status.HTTP_409_CONFLICT,
            )
        teacher_profile = getattr(request.user, "teacher_profile", None)
        if teacher_profile is None:
            return Response(
                {"detail": "Teacher profile not found."}, status=status.HTTP_403_FORBIDDEN
            )
        new_course = CourseService.copy_to_draft(course, teacher_profile)
        return Response(
            CourseService.serialize_course_detail(new_course, context={"request": request}),
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Courses"], summary="Teacher's rejection history (snapshot records)")
class TeacherRejectionRecordsView(generics.ListAPIView):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = RejectedCourseRecordSerializer

    def get_queryset(self):
        teacher_profile = getattr(self.request.user, "teacher_profile", None)
        if teacher_profile is None:
            return RejectedCourseRecord.objects.none()
        return RejectedCourseRecord.objects.filter(teacher_profile=teacher_profile)


@extend_schema(tags=["Courses"], summary="Moderator's rejection history (snapshot records)")
class ModeratorRejectionRecordsView(generics.ListAPIView):
    permission_classes = [IsAdminOrModerator]
    serializer_class = RejectedCourseRecordSerializer

    def get_queryset(self):
        moderator_profile = getattr(self.request.user, "moderator_profile", None)
        if moderator_profile is None:
            return RejectedCourseRecord.objects.none()
        return RejectedCourseRecord.objects.filter(moderator_profile=moderator_profile)


@extend_schema(tags=["Courses"], summary="Moderator's approval history (snapshot records)")
class ModeratorApprovalRecordsView(generics.ListAPIView):
    permission_classes = [IsAdminOrModerator]
    serializer_class = ApprovedCourseRecordSerializer

    def get_queryset(self):
        moderator_profile = getattr(self.request.user, "moderator_profile", None)
        if moderator_profile is None:
            return ApprovedCourseRecord.objects.none()
        return ApprovedCourseRecord.objects.filter(moderator_profile=moderator_profile)
