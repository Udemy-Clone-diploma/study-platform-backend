from datetime import date as date_type

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, CohortMember, Course
from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.enrollments.models import Enrollment
from apps.schedule.models import Attendance, Session

# Only truly active sessions: SCHEDULED status.
# RESCHEDULED = original slot that was moved (replaced by a new SCHEDULED session).
# CANCELLED   = removed entirely.
ACTIVE = Session.Status.SCHEDULED


def _get_course_and_check(view, slug: str) -> Course:
    course = get_course_for_request(view, slug)
    ensure_can_modify_course(view.request.user, course)
    return course


# ── GROUP ─────────────────────────────────────────────────────────────────────

@extend_schema(tags=["Attendance"])
class CohortSessionDatesView(GenericAPIView):
    """GET list of active session dates for a cohort in a given month."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        cohort = get_object_or_404(Cohort, pk=kwargs["cohort_id"], course=course)

        try:
            year  = int(request.query_params.get("year",  timezone.now().year))
            month = int(request.query_params.get("month", timezone.now().month))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year or month."}, status=status.HTTP_400_BAD_REQUEST)

        dates = (
            Session.objects
            .filter(
                Q(schedule__cohort=cohort) | Q(cohort=cohort),
                status=ACTIVE,
                date__year=year,
                date__month=month,
            )
            .values_list("date", flat=True)
            .distinct()
            .order_by("date")
        )
        return Response({"dates": [d.isoformat() for d in dates]})


@extend_schema(tags=["Attendance"])
class CohortAttendanceView(GenericAPIView):
    """GET cohort attendance for a date; POST to mark a student present/absent."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        cohort = get_object_or_404(Cohort, pk=kwargs["cohort_id"], course=course)

        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "date query param required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            session_date = date_type.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "Invalid date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        session = Session.objects.filter(
            Q(schedule__cohort=cohort) | Q(cohort=cohort),
            date=session_date, status=ACTIVE,
        ).first()

        members = list(
            CohortMember.objects.filter(cohort=cohort).select_related(
                "enrollment__student_profile__user",
                "enrollment__course",
            )
        )
        enrollment_ids = [m.enrollment_id for m in members]

        attendance_map: dict[int, bool] = {}
        if session:
            attendance_map = {
                a.enrollment_id: a.is_present
                for a in Attendance.objects.filter(session=session, enrollment_id__in=enrollment_ids)
            }

        # Monthly and all-time attendance — four queries total, no N+1
        now   = timezone.now()
        today = now.date()

        cohort_q = Q(schedule__cohort=cohort) | Q(cohort=cohort)

        month_session_ids = list(
            Session.objects.filter(cohort_q, status=ACTIVE, date__year=now.year, date__month=now.month)
            .values_list("id", flat=True)
        )
        all_session_ids = list(
            Session.objects.filter(cohort_q, status=ACTIVE, date__lte=today)
            .values_list("id", flat=True)
        )

        total_month = len(month_session_ids)
        total_all   = len(all_session_ids)

        def _present_by(session_ids: list) -> dict[int, int]:
            result: dict[int, int] = {}
            for row in (
                Attendance.objects
                .filter(session_id__in=session_ids, enrollment_id__in=enrollment_ids, is_present=True)
                .values("enrollment_id").annotate(cnt=Count("id"))
            ):
                result[row["enrollment_id"]] = row["cnt"]
            return result

        present_month = _present_by(month_session_ids) if total_month else {}
        present_all   = _present_by(all_session_ids)   if total_all   else {}

        result = []
        for member in members:
            enr = member.enrollment
            user = enr.student_profile.user
            total_lessons = enr.course.lessons_count or 0
            result.append({
                "enrollment_id": enr.id,
                "student_id": user.id,
                "student_name": user.get_full_name(),
                "student_email": user.email,
                "student_avatar": absolute_media_url(user.avatar, request),
                "is_present": attendance_map.get(enr.id, False),
                "has_session": session is not None,
                "progress_percent": round(enr.lessons_completed_count / total_lessons * 100) if total_lessons else 0,
                "monthly_attendance_percent": round(present_month.get(enr.id, 0) / total_month * 100) if total_month else 0,
                "total_attendance_percent":   round(present_all.get(enr.id, 0)   / total_all   * 100) if total_all   else 0,
            })
        return Response(result)

    def post(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        cohort = get_object_or_404(Cohort, pk=kwargs["cohort_id"], course=course)

        date_str      = request.data.get("date")
        enrollment_id = request.data.get("enrollment_id")
        is_present    = bool(request.data.get("is_present", True))

        if not date_str or enrollment_id is None:
            return Response({"detail": "date and enrollment_id are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            session_date = date_type.fromisoformat(str(date_str))
        except ValueError:
            return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(
            Session,
            Q(schedule__cohort=cohort) | Q(cohort=cohort),
            date=session_date, status=ACTIVE,
        )
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, cohort_memberships__cohort=cohort)
        attendance, _ = Attendance.objects.update_or_create(
            session=session, enrollment=enrollment,
            defaults={"is_present": is_present},
        )
        return Response({"enrollment_id": enrollment_id, "is_present": attendance.is_present})


# ── INDIVIDUAL ────────────────────────────────────────────────────────────────

@extend_schema(tags=["Attendance"])
class IndividualEnrollmentListView(GenericAPIView):
    """GET students enrolled in the individual delivery format for a course."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        enrollments = (
            Enrollment.objects
            .filter(course=course, delivery_format__format_type="individual")
            .select_related("student_profile__user")
        )
        return Response([
            {
                "enrollment_id": e.id,
                "student_id": e.student_profile.user.id,
                "student_name": e.student_profile.user.get_full_name(),
                "student_email": e.student_profile.user.email,
            }
            for e in enrollments
        ])


@extend_schema(tags=["Attendance"])
class IndividualSessionDatesView(GenericAPIView):
    """GET active session dates for a specific enrolled student (individual format)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        enrollment = get_object_or_404(Enrollment, pk=kwargs["enrollment_id"], course=course)

        try:
            year  = int(request.query_params.get("year",  timezone.now().year))
            month = int(request.query_params.get("month", timezone.now().month))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year or month."}, status=status.HTTP_400_BAD_REQUEST)

        dates = (
            Session.objects
            .filter(slot__booked_by=enrollment, status=ACTIVE, date__year=year, date__month=month)
            .values_list("date", flat=True)
            .distinct()
            .order_by("date")
        )
        return Response({"dates": [d.isoformat() for d in dates]})


@extend_schema(tags=["Attendance"])
class IndividualAttendanceView(GenericAPIView):
    """GET/POST attendance for a single enrolled student on a date."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        enrollment = get_object_or_404(
            Enrollment.objects.select_related("student_profile__user", "course"),
            pk=kwargs["enrollment_id"], course=course,
        )

        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "date query param required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            session_date = date_type.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        session = Session.objects.filter(
            slot__booked_by=enrollment, date=session_date, status=ACTIVE,
        ).first()

        att = None
        if session:
            att = Attendance.objects.filter(session=session, enrollment=enrollment).first()

        # Monthly and all-time attendance
        now   = timezone.now()
        today = now.date()

        month_ids = list(
            Session.objects.filter(
                slot__booked_by=enrollment, status=ACTIVE,
                date__year=now.year, date__month=now.month,
            ).values_list("id", flat=True)
        )
        all_ids = list(
            Session.objects.filter(
                slot__booked_by=enrollment, status=ACTIVE, date__lte=today,
            ).values_list("id", flat=True)
        )

        total_month = len(month_ids)
        total_all   = len(all_ids)

        present_month = (
            Attendance.objects.filter(session_id__in=month_ids, enrollment=enrollment, is_present=True).count()
            if total_month else 0
        )
        present_all = (
            Attendance.objects.filter(session_id__in=all_ids, enrollment=enrollment, is_present=True).count()
            if total_all else 0
        )

        user = enrollment.student_profile.user
        total_lessons = enrollment.course.lessons_count or 0
        return Response([{
            "enrollment_id": enrollment.id,
            "student_id": user.id,
            "student_name": user.get_full_name(),
            "student_email": user.email,
            "student_avatar": absolute_media_url(user.avatar, request),
            "is_present": att.is_present if att else False,
            "has_session": session is not None,
            "progress_percent": round(enrollment.lessons_completed_count / total_lessons * 100) if total_lessons else 0,
            "monthly_attendance_percent": round(present_month / total_month * 100) if total_month else 0,
            "total_attendance_percent":   round(present_all   / total_all   * 100) if total_all   else 0,
        }])

    def post(self, request, *args, **kwargs):
        course = _get_course_and_check(self, kwargs["slug"])
        enrollment = get_object_or_404(Enrollment, pk=kwargs["enrollment_id"], course=course)

        date_str   = request.data.get("date")
        is_present = bool(request.data.get("is_present", True))

        if not date_str:
            return Response({"detail": "date is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            session_date = date_type.fromisoformat(str(date_str))
        except ValueError:
            return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(Session, slot__booked_by=enrollment, date=session_date, status=ACTIVE)
        attendance, _ = Attendance.objects.update_or_create(
            session=session, enrollment=enrollment,
            defaults={"is_present": is_present},
        )
        return Response({"enrollment_id": enrollment.id, "is_present": attendance.is_present})
