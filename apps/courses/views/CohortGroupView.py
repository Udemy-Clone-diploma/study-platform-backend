from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, CohortMember
from apps.courses.serializers.CohortGroupSerializer import (
    CohortMemberSerializer,
    EnrolledStudentSerializer,
)
from apps.curriculum.models import TestAttempt
from apps.enrollments.exceptions import (
    CourseAlreadyCompletedError,
    CourseCompletionNotFoundError,
    CourseNotEligibleForCompletionError,
)
from apps.enrollments.models import CourseCompletion, Enrollment
from apps.enrollments.serializers import CourseCompletionSerializer
from apps.enrollments.services import ProgressService
from apps.homework.models import HomeworkSubmission
from apps.schedule.models import Attendance

from ._course_scoped import ensure_can_modify_course, get_course_for_request


@extend_schema(tags=["Cohort Members"])
class CohortMemberListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        cohort = get_object_or_404(Cohort, pk=self.kwargs["cohort_id"], course=course)

        enrollment_id = request.data.get("enrollment_id")
        if not enrollment_id:
            return Response(
                {"enrollment_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment = get_object_or_404(
            Enrollment.objects.filter(course=course),
            pk=enrollment_id,
        )

        if CohortMember.objects.filter(cohort=cohort, enrollment=enrollment).exists():
            return Response(
                {"detail": "Student is already in this cohort."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if CohortMember.objects.filter(cohort__course=course, enrollment=enrollment).exists():
            return Response(
                {"detail": "Student is already assigned to another cohort of this course."},
                status=status.HTTP_409_CONFLICT,
            )

        member = CohortMember.objects.create(cohort=cohort, enrollment=enrollment)
        return Response(
            CohortMemberSerializer(member, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Cohort Members"])
class CohortMemberDetailView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "member_id"

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        cohort = get_object_or_404(Cohort, pk=self.kwargs["cohort_id"], course=course)
        return CohortMember.objects.filter(cohort=cohort)

    def destroy(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        member = self.get_object()
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Cohort Members"])
class CourseEnrolledStudentsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        qs = Enrollment.objects.filter(course=course).select_related(
            "student_profile__user",
            "delivery_format",
            "course",
        )
        format_id = request.query_params.get("format_id")
        if format_id:
            qs = qs.filter(delivery_format_id=format_id)
        completed_student_profile_ids = set(
            CourseCompletion.objects.filter(course=course).values_list(
                "student_profile_id", flat=True
            )
        )
        status_param = request.query_params.get("status")
        if status_param == "completed":
            qs = qs.filter(student_profile_id__in=completed_student_profile_ids)
        elif status_param == "active":
            qs = qs.exclude(student_profile_id__in=completed_student_profile_ids)
        context = {
            "request": request,
            "completed_student_profile_ids": completed_student_profile_ids,
        }
        return Response(EnrolledStudentSerializer(qs, many=True, context=context).data)


@extend_schema(tags=["Cohort Members"])
class TeacherStudentDashboardView(APIView):
    """Cross-course student analytics, restricted to a teacher's own enrollments."""

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id: int):
        if request.user.role not in {"teacher", "administrator"}:
            return Response({"detail": "Teachers only."}, status=status.HTTP_403_FORBIDDEN)

        enrollment_queryset = Enrollment.objects.filter(
            student_profile__user_id=student_id
        ).select_related("student_profile__user", "course", "course__teacher_profile__user")
        if request.user.role == "teacher":
            enrollment_queryset = enrollment_queryset.filter(
                course__teacher_profile__user=request.user
            )
        all_enrollments = list(enrollment_queryset)
        if not all_enrollments:
            return Response({"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

        selected_course = request.query_params.get("course", "").strip()
        enrollments = (
            [item for item in all_enrollments if item.course.slug == selected_course]
            if selected_course
            else all_enrollments
        )
        if selected_course and not enrollments:
            return Response(
                {"detail": "The student is not enrolled in this course."},
                status=status.HTTP_404_NOT_FOUND,
            )

        student = all_enrollments[0].student_profile
        user = student.user
        enrollment_ids = [item.id for item in enrollments]
        course_ids = [item.course_id for item in enrollments]
        submissions = (
            HomeworkSubmission.objects.filter(enrollment_id__in=enrollment_ids)
            .select_related("assignment__course")
            .order_by("-submitted_at")
        )
        attempts = TestAttempt.objects.filter(
            student_profile=student, test__module__course_id__in=course_ids
        )
        absences = Attendance.objects.filter(
            enrollment_id__in=enrollment_ids, is_present=False
        ).count()

        today = timezone.localdate()
        week_points = []
        for offset in range(5, -1, -1):
            week_start = today - timedelta(days=today.weekday() + offset * 7)
            week_end = week_start + timedelta(days=7)
            average = submissions.filter(
                reviewed_at__date__gte=week_start,
                reviewed_at__date__lt=week_end,
                score__isnull=False,
            ).aggregate(value=Avg("score"))["value"]
            week_points.append(
                {
                    "label": f"Week {6 - offset}",
                    "value": round(float(average), 1) if average is not None else 0,
                }
            )

        activities = [
            {
                "id": submission.id,
                "assignment_id": submission.assignment_id,
                "course_slug": submission.assignment.course.slug,
                "course": submission.assignment.course.title,
                "kind": "Test" if submission.assignment.test_id else "Task",
                "title": submission.assignment.title,
                "date": submission.submitted_at.date().isoformat(),
                "score": submission.score,
                "status": submission.status,
            }
            for submission in submissions[:30]
        ]
        courses = []
        for enrollment in all_enrollments:
            total = enrollment.course.lessons_count
            progress = round(enrollment.lessons_completed_count / total * 100) if total else 0
            courses.append(
                {
                    "slug": enrollment.course.slug,
                    "title": enrollment.course.title,
                    "teacher": enrollment.course.teacher_profile.user.get_full_name(),
                    "image": absolute_media_url(enrollment.course.image, request),
                    "progress": progress,
                }
            )

        reviewed_scores = [point["value"] for point in week_points if point["value"] > 0]
        return Response(
            {
                "profile": {
                    "id": user.id,
                    "name": user.get_full_name() or user.email,
                    "email": user.email,
                    "avatar": absolute_media_url(user.avatar, request),
                    "socials": {
                        key: getattr(user, key)
                        for key in ("instagram", "linkedin", "facebook", "behance")
                    },
                },
                "metrics": {
                    "homeworks_done": submissions.count(),
                    "tests_done": attempts.values("test_id").distinct().count(),
                    "absences": absences,
                },
                "activities": activities,
                "growth": {
                    "average": round(sum(reviewed_scores) / len(reviewed_scores), 1)
                    if reviewed_scores
                    else 0,
                    "points": week_points,
                },
                "courses": courses,
            }
        )


@extend_schema(tags=["Cohort Members"])
class EnrollmentCompleteView(APIView):
    """Teacher/admin action to mark a student's learning as finished, for
    delivery formats (group/individual) that may have no curriculum lessons
    at all, where the student-facing `POST .../completions/` can never be
    eligible."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, enrollment_id: int):
        course = get_course_for_request(self, slug)
        ensure_can_modify_course(request.user, course)
        enrollment = get_object_or_404(Enrollment.objects.filter(course=course), pk=enrollment_id)

        try:
            completion = ProgressService.teacher_complete_course(course, enrollment)
        except CourseNotEligibleForCompletionError:
            return Response(
                {"detail": "This student has not yet met this course's completion requirements."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except CourseAlreadyCompletedError:
            return Response(
                {"detail": "Course already completed."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            CourseCompletionSerializer(completion, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, slug: str, enrollment_id: int):
        """Undo a teacher-initiated completion, returning the student to active study."""
        course = get_course_for_request(self, slug)
        ensure_can_modify_course(request.user, course)
        enrollment = get_object_or_404(Enrollment.objects.filter(course=course), pk=enrollment_id)

        try:
            ProgressService.teacher_revert_completion(course, enrollment)
        except CourseCompletionNotFoundError:
            return Response(
                {"detail": "This student hasn't completed the course."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
