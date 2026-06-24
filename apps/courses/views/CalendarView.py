import calendar as _cal
from datetime import date, timedelta

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import CohortSchedule, ScheduleSlot, TeacherUnavailability
from apps.courses.serializers import TeacherUnavailabilitySerializer
from apps.users.models import User


def _week_monday(week_start_str: str | None) -> date:
    """Return the Monday of the week containing the given ISO date, or current week."""
    try:
        d = date.fromisoformat(week_start_str or "")
    except (ValueError, TypeError, AttributeError):
        d = date.today()
    return d - timedelta(days=d.weekday())


def _fmt(t) -> str:
    return str(t)[:5]


def _date_iso(monday: date, day_of_week: int) -> str:
    """Convert backend day_of_week (0=Mon…6=Sun) to a specific date in the week."""
    return (monday + timedelta(days=day_of_week)).isoformat()


def _add_months(d: date, months: int) -> date:
    """Add a number of months to a date, clamping to the last day of the target month."""
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _enrollment_active_on(enrollment, event_date: date) -> bool:
    """True if event_date falls within the enrollment's access window."""
    start = enrollment.access_granted_at.date()
    if event_date < start:
        return False
    if enrollment.access_until is not None:
        if event_date > enrollment.access_until.date():
            return False
    return True


def _period_active_on(start_date, duration_months: int | None, event_date: date) -> bool:
    if not start_date:
        return True
    if event_date < start_date:
        return False
    if duration_months:
        if event_date > _add_months(start_date, duration_months):
            return False
    return True


def _build_slot_event(slot, monday: date, *, student=None, is_available) -> dict:
    return {
        "id": f"slot_{slot.id}",
        "type": "individual_session",
        "date": _date_iso(monday, slot.day_of_week),
        "start_time": _fmt(slot.start_time),
        "end_time": _fmt(slot.end_time),
        "course_title": slot.delivery_format.course.title,
        "course_slug": slot.delivery_format.course.slug,
        "student": student,
        "cohort_name": None,
        "meeting_link": slot.meeting_link or None,
        "is_available": is_available,
    }


def _build_cohort_event(sched, event_date: date) -> dict:
    return {
        "id": f"group_{sched.id}",
        "type": "group_session",
        "date": event_date.isoformat(),
        "start_time": _fmt(sched.start_time),
        "end_time": _fmt(sched.end_time),
        "course_title": sched.cohort.course.title,
        "course_slug": sched.cohort.course.slug,
        "student": None,
        "cohort_name": sched.cohort.name or f"Cohort #{sched.cohort.id}",
        "meeting_link": sched.meeting_link or None,
        "is_available": None,
    }


@extend_schema(
    tags=["Calendar"],
    parameters=[
        OpenApiParameter("week_start", str, description="ISO date of any day in the desired week"),
    ],
)
class CalendarView(APIView):
    """
    Returns calendar events and (for teachers) unavailability blocks for the requested week.

    week_start: any ISO date — the view normalises it to Monday of that week.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        monday = _week_monday(request.query_params.get("week_start"))
        user = request.user

        if user.role == User.RoleChoices.TEACHER:
            events = self._teacher_events(user, monday)
            unavailability = TeacherUnavailabilitySerializer(
                TeacherUnavailability.objects.filter(teacher_profile=user.teacher_profile),
                many=True,
                context={"request": request},
            ).data
        elif user.role == User.RoleChoices.STUDENT:
            events = self._student_events(user, monday)
            unavailability = []
        else:
            events = []
            unavailability = []

        return Response({
            "week_start": monday.isoformat(),
            "events": events,
            "unavailability": unavailability,
        })

    # ── Teacher ────────────────────────────────────────────────────────────────

    def _teacher_events(self, user, monday: date) -> list:
        events = []

        slots = (
            ScheduleSlot.objects
            .filter(delivery_format__course__teacher_profile=user.teacher_profile)
            .select_related("delivery_format__course", "booked_by__student_profile__user")
        )
        for slot in slots:
            event_date = monday + timedelta(days=slot.day_of_week)
            if slot.booked_by_id and not _enrollment_active_on(slot.booked_by, event_date):
                continue
            student = None
            if slot.booked_by_id:
                u = slot.booked_by.student_profile.user
                student = {"name": u.get_full_name() or u.email, "email": u.email}
            events.append(_build_slot_event(slot, monday, student=student, is_available=slot.is_available))

        cohort_schedules = (
            CohortSchedule.objects
            .filter(cohort__course__teacher_profile=user.teacher_profile)
            .select_related("cohort__course")
        )
        for sched in cohort_schedules:
            event_date = monday + timedelta(days=sched.day_of_week)
            if _period_active_on(sched.cohort.start_date, sched.cohort.duration_months, event_date):
                events.append(_build_cohort_event(sched, event_date))

        return events

    # ── Student ────────────────────────────────────────────────────────────────

    def _student_events(self, user, monday: date) -> list:
        events = []

        slots = (
            ScheduleSlot.objects
            .filter(booked_by__student_profile=user.student_profile)
            .select_related("delivery_format__course", "booked_by")
        )
        for slot in slots:
            event_date = monday + timedelta(days=slot.day_of_week)
            if not _enrollment_active_on(slot.booked_by, event_date):
                continue
            events.append(_build_slot_event(slot, monday, is_available=False))

        cohort_schedules = (
            CohortSchedule.objects
            .filter(cohort__members__enrollment__student_profile=user.student_profile)
            .select_related("cohort__course")
            .distinct()
        )
        for sched in cohort_schedules:
            event_date = monday + timedelta(days=sched.day_of_week)
            if _period_active_on(sched.cohort.start_date, sched.cohort.duration_months, event_date):
                events.append(_build_cohort_event(sched, event_date))

        return events
