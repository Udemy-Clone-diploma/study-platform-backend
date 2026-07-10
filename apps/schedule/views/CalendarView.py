import calendar as _cal
from datetime import date, datetime, timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.enrollments.models import Enrollment
from apps.homework.models import HomeworkAssignment
from apps.schedule.models import (
    CohortSchedule, EventInvitation, PersonalEvent, ScheduleSlot,
    Session, TeacherUnavailability,
)
from apps.schedule.serializers import TeacherUnavailabilitySerializer
from apps.schedule.services import ScheduleNotificationService
from apps.users.models import User


# ── Helpers ────────────────────────────────────────────────────────────────────

def _teacher_unavailable_on(teacher_profile, event_date: date, start_time, end_time) -> bool:
    """Return True if any unavailability block covers the given date and time window."""
    time_q = Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
    return TeacherUnavailability.objects.filter(
        time_q,
        teacher_profile=teacher_profile,
    ).filter(
        Q(recurrence_type=TeacherUnavailability.RecurrenceType.WEEKLY,
          day_of_week=event_date.weekday())
        | Q(recurrence_type=TeacherUnavailability.RecurrenceType.ONE_TIME,
            date=event_date)
        | Q(recurrence_type=TeacherUnavailability.RecurrenceType.DATE_RANGE,
            date__lte=event_date, date_to__gte=event_date)
    ).exists()


def _default_week_start() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _week_bounds(week_start_str: str | None) -> tuple[date, date]:
    if week_start_str:
        try:
            week_start = date.fromisoformat(week_start_str)
        except (ValueError, TypeError):
            week_start = _default_week_start()
    else:
        week_start = _default_week_start()
    return week_start, week_start + timedelta(days=6)


def _event_date_for_slot(week_start: date, week_end: date, day_of_week: int) -> date | None:
    monday = week_start - timedelta(days=week_start.weekday())
    for extra in (0, 7):
        candidate = monday + timedelta(days=day_of_week + extra)
        if week_start <= candidate <= week_end:
            return candidate
    return None


def _fmt(t) -> str:
    return str(t)[:5]


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _enrollment_active_on(enrollment, event_date: date) -> bool:
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


# ── Event builders ─────────────────────────────────────────────────────────────

def _build_session_event(session: Session, *, slot=None, sched=None, student=None, is_available=None) -> dict:
    if slot:
        event_type   = "individual_session"
        course_title = slot.delivery_format.course.title
        course_slug  = slot.delivery_format.course.slug
        cohort_name  = None
    elif sched:
        event_type   = "group_session"
        course_title = sched.cohort.course.title
        course_slug  = sched.cohort.course.slug
        cohort_name  = sched.cohort.name or f"Cohort #{sched.cohort.id}"
    else:
        event_type   = "extra_session"
        course_title = session.course.title if session.course_id else None
        course_slug  = session.course.slug  if session.course_id else None
        cohort_name  = (session.cohort.name or f"Cohort #{session.cohort.id}") if session.cohort_id else None
        if session.student_profile_id and student is None:
            u = session.student_profile.user
            student = {"name": u.get_full_name() or u.email, "email": u.email}

    status_val = session.status if session.status != Session.Status.SCHEDULED else None

    return {
        "id":                    f"session_{session.id}",
        "type":                  event_type,
        "date":                  session.date.isoformat(),
        "start_time":            _fmt(session.start_time),
        "end_time":              _fmt(session.end_time),
        "course_title":          course_title,
        "course_slug":           course_slug,
        "student":               student,
        "cohort_name":           cohort_name,
        "meeting_link":          session.meeting_link,
        "lesson_title":          session.lesson.title if session.lesson_id else None,
        "lesson_url":            None,
        "is_available":          is_available,
        "event_status":          status_val,
        "rescheduled_to_date":   session.rescheduled_to_date.isoformat() if session.rescheduled_to_date else None,
        "rescheduled_from_date": session.rescheduled_from_date.isoformat() if session.rescheduled_from_date else None,
    }


def _build_personal_event(
    event: PersonalEvent,
    *,
    invitation: EventInvitation | None = None,
    event_type: str = "personal",
) -> dict:
    final_type = "personal_shared" if invitation else event_type
    owner = event.owner
    return {
        "id":           f"personal_{event.id}",
        "type":         final_type,
        "date":         event.date.isoformat(),
        "start_time":   _fmt(event.start_time),
        "end_time":     _fmt(event.end_time),
        "title":        event.title,
        "owner_name":   owner.get_full_name() or owner.email,
        "meeting_link": event.meeting_link,
        "is_owner":     invitation is None,
        "invite_status": invitation.status if invitation else None,
        "course_title":          None,
        "course_slug":           None,
        "student":               None,
        "cohort_name":           None,
        "lesson_title":          None,
        "lesson_url":            None,
        "is_available":          None,
        "event_status":          None,
        "rescheduled_to_date":   None,
        "rescheduled_from_date": None,
    }


# ── Bulk session loader ────────────────────────────────────────────────────────

def _get_or_create_sessions(
    slots, cohort_schedules, week_start: date, week_end: date
) -> tuple[dict, dict]:
    slot_ids  = [s.id for s in slots]
    sched_ids = [s.id for s in cohort_schedules]

    existing_slot  = {}
    existing_sched = {}

    if slot_ids:
        for sess in Session.objects.filter(
            slot_id__in=slot_ids,
            date__range=[week_start, week_end],
            rescheduled_from_date__isnull=True,
        ).select_related("lesson"):
            existing_slot[(sess.slot_id, sess.date)] = sess

    if sched_ids:
        for sess in Session.objects.filter(
            schedule_id__in=sched_ids,
            date__range=[week_start, week_end],
            rescheduled_from_date__isnull=True,
        ).select_related("lesson"):
            existing_sched[(sess.schedule_id, sess.date)] = sess

    return existing_slot, existing_sched


def _load_replacement_sessions(
    slot_ids, sched_ids, week_start: date, week_end: date, built_ids: set
) -> list[Session]:
    qs = Session.objects.filter(
        rescheduled_from_date__isnull=False,
        date__range=[week_start, week_end],
    ).select_related(
        "slot__delivery_format__course",
        "slot__booked_by__student_profile__user",
        "schedule__cohort__course",
        "lesson",
    )
    if slot_ids and sched_ids:
        qs = qs.filter(Q(slot_id__in=slot_ids) | Q(schedule_id__in=sched_ids))
    elif slot_ids:
        qs = qs.filter(slot_id__in=slot_ids)
    elif sched_ids:
        qs = qs.filter(schedule_id__in=sched_ids)
    else:
        return []
    return [s for s in qs if s.id not in built_ids]


# ── Views ──────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=["Calendar"],
    parameters=[OpenApiParameter("week_start", str, description="ISO date of any day in the desired week")],
)
class CalendarView(APIView):
    """Returns calendar events and (for teachers) unavailability for the requested week."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        week_start, week_end = _week_bounds(request.query_params.get("week_start"))
        user = request.user

        if user.role == User.RoleChoices.TEACHER:
            events = self._teacher_events(user, week_start, week_end)
            unavailability = TeacherUnavailabilitySerializer(
                TeacherUnavailability.objects.filter(teacher_profile=user.teacher_profile),
                many=True,
                context={"request": request},
            ).data
        elif user.role == User.RoleChoices.STUDENT:
            events = self._student_events(user, week_start, week_end)
            unavailability = []
        else:
            events, unavailability = [], []

        deadlines = self._deadlines_for(user, week_start, week_end)

        return Response({
            "week_start": week_start.isoformat(),
            "events": events,
            "unavailability": unavailability,
            "deadlines": deadlines,
        })

    def _deadlines_for(self, user, week_start: date, week_end: date) -> list:
        if user.role != User.RoleChoices.STUDENT:
            return []

        active_enrollments = Enrollment.objects.with_active_access().exclude_completed().filter(
            student_profile=user.student_profile
        )
        assignments = HomeworkAssignment.objects.filter(
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
            recipients__enrollment__in=active_enrollments,
            due_at__date__range=[week_start, week_end],
        ).select_related("course").distinct()

        return [
            {
                "date": a.due_at.date().isoformat(),
                "assignment_id": a.id,
                "title": a.title,
                "course_title": a.course.title,
                "course_slug": a.course.slug,
            }
            for a in assignments
        ]

    def _teacher_events(self, user, week_start: date, week_end: date) -> list:
        teacher_profile = user.teacher_profile
        slots = list(
            ScheduleSlot.objects
            .filter(delivery_format__course__teacher_profile=teacher_profile)
            .select_related("delivery_format__course", "booked_by__student_profile__user")
        )
        cohort_schedules = list(
            CohortSchedule.objects
            .filter(cohort__course__teacher_profile=teacher_profile)
            .select_related("cohort__course")
        )

        existing_slot, existing_sched = _get_or_create_sessions(slots, cohort_schedules, week_start, week_end)
        events = []
        built_ids = set()
        slot_map  = {}
        sched_map = {}

        for slot in slots:
            event_date = _event_date_for_slot(week_start, week_end, slot.day_of_week)
            if event_date is None:
                continue
            if slot.booked_by_id and not _enrollment_active_on(slot.booked_by, event_date):
                continue

            session = existing_slot.get((slot.id, event_date))
            if session is None:
                unavailable = _teacher_unavailable_on(
                    teacher_profile, event_date, slot.start_time, slot.end_time
                )
                session = Session.objects.create(
                    slot=slot, date=event_date,
                    start_time=slot.start_time, end_time=slot.end_time,
                    status=Session.Status.CANCELLED if unavailable else Session.Status.SCHEDULED,
                )

            student = None
            if slot.booked_by_id:
                u = slot.booked_by.student_profile.user
                student = {"name": u.get_full_name() or u.email, "email": u.email}

            events.append(_build_session_event(session, slot=slot, student=student, is_available=slot.is_available))
            built_ids.add(session.id)
            slot_map[slot.id] = (slot, student)

        for sched in cohort_schedules:
            event_date = _event_date_for_slot(week_start, week_end, sched.day_of_week)
            if event_date is None:
                continue
            if not _period_active_on(sched.cohort.start_date, sched.cohort.duration_months, event_date):
                continue

            session = existing_sched.get((sched.id, event_date))
            if session is None:
                unavailable = _teacher_unavailable_on(
                    teacher_profile, event_date, sched.start_time, sched.end_time
                )
                session = Session.objects.create(
                    schedule=sched, date=event_date,
                    start_time=sched.start_time, end_time=sched.end_time,
                    status=Session.Status.CANCELLED if unavailable else Session.Status.SCHEDULED,
                )

            events.append(_build_session_event(session, sched=sched))
            built_ids.add(session.id)
            sched_map[sched.id] = sched

        for session in _load_replacement_sessions(
            [s.id for s in slots], [s.id for s in cohort_schedules], week_start, week_end, built_ids
        ):
            if session.slot_id and session.slot_id in dict(slot_map):
                slot, student = slot_map[session.slot_id]
                events.append(_build_session_event(session, slot=slot, student=student, is_available=slot.is_available))
            elif session.schedule_id and session.schedule_id in sched_map:
                events.append(_build_session_event(session, sched=sched_map[session.schedule_id]))

        extra_sessions = (
            Session.objects
            .filter(
                course__teacher_profile=user.teacher_profile,
                date__range=[week_start, week_end],
                slot__isnull=True,
                schedule__isnull=True,
            )
            .select_related("course", "cohort", "student_profile__user", "lesson")
        )
        for session in extra_sessions:
            events.append(_build_session_event(session))

        events.extend(self._personal_events(user, week_start, week_end))
        return events

    def _student_events(self, user, week_start: date, week_end: date) -> list:
        # Excludes finished courses: a completed group enrollment's cohort
        # session should stop appearing for that student even though other
        # (still-studying) cohort members keep meeting. Individual slots don't
        # need this -- completion already frees `ScheduleSlot.booked_by`
        # (apps/enrollments/signals.py:course_completion_created).
        active_enrollments = Enrollment.objects.with_active_access().exclude_completed().filter(
            student_profile=user.student_profile,
        )

        slots = list(
            ScheduleSlot.objects
            .filter(booked_by__student_profile=user.student_profile)
            .select_related(
                "delivery_format__course__teacher_profile",
                "booked_by",
            )
        )
        cohort_schedules = list(
            CohortSchedule.objects
            .filter(cohort__members__enrollment__in=active_enrollments)
            .select_related("cohort__course__teacher_profile")
            .distinct()
        )

        existing_slot, existing_sched = _get_or_create_sessions(slots, cohort_schedules, week_start, week_end)
        events = []
        built_ids = set()
        slot_map  = {}
        sched_map = {}

        for slot in slots:
            event_date = _event_date_for_slot(week_start, week_end, slot.day_of_week)
            if event_date is None:
                continue
            if not _enrollment_active_on(slot.booked_by, event_date):
                continue

            session = existing_slot.get((slot.id, event_date))
            if session is None:
                teacher = slot.delivery_format.course.teacher_profile
                unavailable = _teacher_unavailable_on(
                    teacher, event_date, slot.start_time, slot.end_time
                )
                session = Session.objects.create(
                    slot=slot, date=event_date,
                    start_time=slot.start_time, end_time=slot.end_time,
                    status=Session.Status.CANCELLED if unavailable else Session.Status.SCHEDULED,
                )

            events.append(_build_session_event(session, slot=slot, is_available=False))
            built_ids.add(session.id)
            slot_map[slot.id] = slot

        for sched in cohort_schedules:
            event_date = _event_date_for_slot(week_start, week_end, sched.day_of_week)
            if event_date is None:
                continue
            if not _period_active_on(sched.cohort.start_date, sched.cohort.duration_months, event_date):
                continue

            session = existing_sched.get((sched.id, event_date))
            if session is None:
                teacher = sched.cohort.course.teacher_profile
                unavailable = _teacher_unavailable_on(
                    teacher, event_date, sched.start_time, sched.end_time
                )
                session = Session.objects.create(
                    schedule=sched, date=event_date,
                    start_time=sched.start_time, end_time=sched.end_time,
                    status=Session.Status.CANCELLED if unavailable else Session.Status.SCHEDULED,
                )

            events.append(_build_session_event(session, sched=sched))
            built_ids.add(session.id)
            sched_map[sched.id] = sched

        for session in _load_replacement_sessions(
            [s.id for s in slots], [s.id for s in cohort_schedules], week_start, week_end, built_ids
        ):
            if session.slot_id and session.slot_id in slot_map:
                events.append(_build_session_event(session, slot=slot_map[session.slot_id], is_available=False))
            elif session.schedule_id and session.schedule_id in sched_map:
                events.append(_build_session_event(session, sched=sched_map[session.schedule_id]))

        extra_sessions = (
            Session.objects
            .filter(
                course__isnull=False,
                date__range=[week_start, week_end],
                slot__isnull=True,
                schedule__isnull=True,
            )
            .filter(
                Q(student_profile=user.student_profile)
                | Q(cohort__members__enrollment__in=active_enrollments)
            )
            .select_related("course", "cohort", "student_profile__user", "lesson")
            .distinct()
        )
        for session in extra_sessions:
            events.append(_build_session_event(session))

        events.extend(self._personal_events(user, week_start, week_end))
        return events

    def _personal_events(self, user, week_start: date, week_end: date) -> list:
        events = []

        own_events = PersonalEvent.objects.filter(
            owner=user, date__range=[week_start, week_end],
        ).select_related("owner").annotate(
            has_invites=Exists(EventInvitation.objects.filter(event=OuterRef("pk")))
        )
        for ev in own_events:
            et = "personal_shared" if ev.has_invites else "personal"
            events.append(_build_personal_event(ev, event_type=et))

        for inv in (
            EventInvitation.objects
            .filter(invitee=user, status=EventInvitation.Status.ACCEPTED, event__date__range=[week_start, week_end])
            .select_related("event__owner")
        ):
            events.append(_build_personal_event(inv.event, invitation=inv))

        return events


# ── Personal Event CRUD ────────────────────────────────────────────────────────

def _check_personal_event_conflicts(user, ev_date, start_t, end_t, exclude_event_id=None):
    time_q = Q(start_time__lt=end_t) & Q(end_time__gt=start_t)
    conflicts = []

    own_qs = PersonalEvent.objects.filter(Q(owner=user) & Q(date=ev_date) & time_q)
    if exclude_event_id:
        own_qs = own_qs.exclude(pk=exclude_event_id)
    for e in own_qs:
        conflicts.append({"type": "personal", "title": e.title,
                          "start_time": _fmt(e.start_time), "end_time": _fmt(e.end_time)})

    # Check accepted invitations to other people's events
    inv_time_q = Q(event__start_time__lt=end_t) & Q(event__end_time__gt=start_t)
    accepted_inv_qs = EventInvitation.objects.filter(
        inv_time_q,
        invitee=user,
        status=EventInvitation.Status.ACCEPTED,
        event__date=ev_date,
    ).select_related("event")
    if exclude_event_id:
        accepted_inv_qs = accepted_inv_qs.exclude(event_id=exclude_event_id)
    for inv in accepted_inv_qs:
        conflicts.append({"type": "shared_event", "title": inv.event.title,
                          "start_time": _fmt(inv.event.start_time), "end_time": _fmt(inv.event.end_time)})

    if hasattr(user, "teacher_profile"):
        tp = user.teacher_profile
        ev_weekday = ev_date.weekday()
        day_q = Q(day_of_week=ev_weekday)

        inactive_slot = Session.objects.filter(
            slot=OuterRef("pk"), date=ev_date,
            status__in=[Session.Status.CANCELLED, Session.Status.RESCHEDULED],
        )
        for slot in ScheduleSlot.objects.filter(
            day_q & time_q & Q(booked_by__isnull=False),
            delivery_format__course__teacher_profile=tp,
        ).exclude(Exists(inactive_slot)).select_related("delivery_format__course"):
            conflicts.append({"type": "individual", "title": slot.delivery_format.course.title,
                               "start_time": _fmt(slot.start_time), "end_time": _fmt(slot.end_time)})

        inactive_sched = Session.objects.filter(
            schedule=OuterRef("pk"), date=ev_date,
            status__in=[Session.Status.CANCELLED, Session.Status.RESCHEDULED],
        )
        for sched in CohortSchedule.objects.filter(
            day_q & time_q,
            cohort__course__teacher_profile=tp,
        ).exclude(Exists(inactive_sched)).select_related("cohort__course"):
            conflicts.append({"type": "group", "title": sched.cohort.course.title,
                               "start_time": _fmt(sched.start_time), "end_time": _fmt(sched.end_time)})

    return conflicts


@extend_schema(tags=["Calendar"])
class PersonalEventView(APIView):
    """POST /calendar/events/personal/ — create a personal event."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from datetime import date as _date, time as _time
        data = request.data
        required = ("title", "date", "start_time", "end_time")
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response({"detail": f"Missing fields: {', '.join(missing)}"}, status=400)

        try:
            ev_date = _date.fromisoformat(data["date"])
            sh, sm = map(int, data["start_time"].split(":"))
            eh, em = map(int, data["end_time"].split(":"))
            start_t = _time(sh, sm)
            end_t   = _time(eh, em)
        except (ValueError, AttributeError):
            return Response({"detail": "Invalid date or time."}, status=400)

        conflicts = _check_personal_event_conflicts(request.user, ev_date, start_t, end_t)
        if conflicts:
            return Response({"detail": "Time conflict with existing events.", "conflicts": conflicts}, status=409)

        try:
            ev = PersonalEvent.objects.create(
                owner=request.user,
                title=data["title"],
                date=ev_date,
                start_time=start_t,
                end_time=end_t,
                meeting_link=data.get("meeting_link") or None,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"status": "created", "id": f"personal_{ev.id}"}, status=201)


@extend_schema(tags=["Calendar"])
class PersonalEventDetailView(APIView):
    """PATCH/DELETE /calendar/events/personal/{id}/"""

    permission_classes = [IsAuthenticated]

    def _get_event(self, pk, user):
        try:
            return PersonalEvent.objects.get(pk=pk, owner=user)
        except PersonalEvent.DoesNotExist:
            return None

    def patch(self, request, pk: int):
        from datetime import date as _date, time as _time
        ev = self._get_event(pk, request.user)
        if not ev:
            return Response({"detail": "Not found"}, status=404)

        data = request.data

        try:
            ev_date = _date.fromisoformat(data["date"]) if "date" in data else ev.date
            start_str = data.get("start_time", _fmt(ev.start_time))
            end_str   = data.get("end_time",   _fmt(ev.end_time))
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            start_t = _time(sh, sm)
            end_t   = _time(eh, em)
        except (ValueError, AttributeError):
            return Response({"detail": "Invalid date or time."}, status=400)

        time_changed = "date" in data or "start_time" in data or "end_time" in data

        if time_changed:
            conflicts = _check_personal_event_conflicts(
                request.user, ev_date, start_t, end_t, exclude_event_id=pk
            )
            if conflicts:
                return Response({"detail": "Time conflict with existing events.", "conflicts": conflicts}, status=409)

        for field in ("title", "date", "start_time", "end_time", "meeting_link"):
            if field in data:
                setattr(ev, field, data[field] or None if field == "meeting_link" else data[field])
        ev.save()

        reset_invitees = []
        if time_changed:
            affected = (
                EventInvitation.objects
                .filter(event=ev, status=EventInvitation.Status.ACCEPTED)
                .select_related("invitee")
            )
            invitee_users = []
            for inv in affected:
                inv.status = EventInvitation.Status.PENDING
                inv.responded_at = None
                inv.save(update_fields=["status", "responded_at"])
                reset_invitees.append(inv.invitee.email)
                invitee_users.append(inv.invitee)
            if invitee_users:
                ScheduleNotificationService.notify_event_rescheduled(ev, invitee_users, actor=request.user)

        return Response({"status": "ok", "reset_invitations": reset_invitees})

    def delete(self, request, pk: int):
        ev = self._get_event(pk, request.user)
        if not ev:
            return Response({"detail": "Not found"}, status=404)
        invitee_users = [
            inv.invitee for inv in
            EventInvitation.objects.filter(
                event=ev, status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.ACCEPTED],
            ).select_related("invitee")
        ]
        ev.delete()
        if invitee_users:
            ScheduleNotificationService.notify_event_cancelled(ev, invitee_users, actor=request.user)
        return Response(status=204)


@extend_schema(tags=["Calendar"])
class PersonalEventConflictView(APIView):
    """
    GET /calendar/events/personal/conflicts/
    ?date=YYYY-MM-DD&start_time=HH:MM&end_time=HH:MM[&exclude_id=N][&include_free_slots=true]
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str  = request.query_params.get("date")
        start_str = request.query_params.get("start_time")
        end_str   = request.query_params.get("end_time")
        if not (date_str and start_str and end_str):
            return Response({"detail": "date, start_time, end_time are required."}, status=400)
        try:
            ev_date = date.fromisoformat(date_str)
            from datetime import time as time_type
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            start_t = time_type(sh, sm)
            end_t   = time_type(eh, em)
        except (ValueError, AttributeError):
            return Response({"detail": "Invalid date or time."}, status=400)

        exclude_id = request.query_params.get("exclude_id")
        include_free_slots = request.query_params.get("include_free_slots") == "true"

        user = request.user
        ev_weekday = ev_date.weekday()
        time_q = Q(start_time__lt=end_t) & Q(end_time__gt=start_t)

        session_list = []

        if hasattr(user, "teacher_profile"):
            tp = user.teacher_profile

            inactive_for_sched = Session.objects.filter(
                schedule=OuterRef("pk"),
                date=ev_date,
                status__in=[Session.Status.CANCELLED, Session.Status.RESCHEDULED],
            )
            for sched in CohortSchedule.objects.filter(
                time_q & Q(day_of_week=ev_weekday),
                cohort__course__teacher_profile=tp,
            ).exclude(Exists(inactive_for_sched)).select_related("cohort__course"):
                session_list.append({
                    "id": f"sched_{sched.id}",
                    "title": sched.cohort.course.title,
                    "type": "group",
                    "start_time": sched.start_time.strftime("%H:%M"),
                    "end_time":   sched.end_time.strftime("%H:%M"),
                })

            inactive_for_slot = Session.objects.filter(
                slot=OuterRef("pk"),
                date=ev_date,
                status__in=[Session.Status.CANCELLED, Session.Status.RESCHEDULED],
            )
            for slot in ScheduleSlot.objects.filter(
                time_q & Q(day_of_week=ev_weekday) & Q(booked_by__isnull=False),
                delivery_format__course__teacher_profile=tp,
            ).exclude(Exists(inactive_for_slot)).select_related("delivery_format__course"):
                session_list.append({
                    "id": f"slot_{slot.id}",
                    "title": slot.delivery_format.course.title,
                    "type": "individual",
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time":   slot.end_time.strftime("%H:%M"),
                })

            if include_free_slots:
                for slot in ScheduleSlot.objects.filter(
                    time_q & Q(day_of_week=ev_weekday) & Q(booked_by__isnull=True),
                    delivery_format__course__teacher_profile=tp,
                ).exclude(Exists(inactive_for_slot)).select_related("delivery_format__course"):
                    session_list.append({
                        "id": f"slot_{slot.id}",
                        "title": slot.delivery_format.course.title,
                        "type": "individual",
                        "start_time": slot.start_time.strftime("%H:%M"),
                        "end_time":   slot.end_time.strftime("%H:%M"),
                    })

            for s in Session.objects.filter(
                time_q & Q(date=ev_date) & Q(status=Session.Status.SCHEDULED),
                schedule__isnull=True, slot__isnull=True,
                course__teacher_profile=tp,
            ).select_related("course"):
                session_list.append({
                    "id": s.id,
                    "title": s.course.title if s.course_id else "Session",
                    "type": "extra",
                    "start_time": s.start_time.strftime("%H:%M"),
                    "end_time":   s.end_time.strftime("%H:%M"),
                })

        elif hasattr(user, "student_profile"):
            session_q = Q(date=ev_date, status=Session.Status.SCHEDULED) & time_q
            for s in Session.objects.filter(
                session_q,
                student_profile=user.student_profile,
            ).select_related("course", "cohort", "schedule", "slot"):
                session_list.append({
                    "id": s.id,
                    "title": s.course.title if s.course_id else "Session",
                    "type": "group" if s.schedule_id else "individual",
                    "start_time": s.start_time.strftime("%H:%M"),
                    "end_time":   s.end_time.strftime("%H:%M"),
                })

        personal_qs = PersonalEvent.objects.filter(
            Q(owner=user) & Q(date=ev_date) & time_q
        )
        if exclude_id:
            try:
                personal_qs = personal_qs.exclude(pk=int(exclude_id))
            except ValueError:
                pass
        personal_list = [
            {"id": e.id, "title": e.title, "start_time": e.start_time.strftime("%H:%M"), "end_time": e.end_time.strftime("%H:%M")}
            for e in personal_qs
        ]

        inv_q = Q(
            invitee=user,
            status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.ACCEPTED],
            event__date=ev_date,
        ) & Q(event__start_time__lt=end_t) & Q(event__end_time__gt=start_t)
        for inv in EventInvitation.objects.filter(inv_q).select_related("event"):
            personal_list.append({
                "id": inv.event_id,
                "title": inv.event.title,
                "start_time": inv.event.start_time.strftime("%H:%M"),
                "end_time":   inv.event.end_time.strftime("%H:%M"),
                "is_invite": True,
                "invitation_id": inv.id,
            })

        return Response({"sessions": session_list, "personal_events": personal_list})


# ── Extra sessions (manually created by teacher) ──────────────────────────────

@extend_schema(tags=["Calendar"])
class ExtraSessionView(APIView):
    """POST /calendar/events/extra/ — teacher creates an extra lesson outside the main schedule."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != User.RoleChoices.TEACHER:
            return Response({"detail": "Only teachers can create extra sessions"}, status=403)

        data = request.data
        required = ("date", "start_time", "end_time", "course_id")
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response({"detail": f"Missing fields: {', '.join(missing)}"}, status=400)

        from apps.courses.models import Course, Cohort
        from apps.users.models import StudentProfile

        try:
            course = Course.objects.get(pk=data["course_id"], teacher_profile=user.teacher_profile)
        except Course.DoesNotExist:
            return Response({"detail": "Course not found or not yours"}, status=404)

        cohort = None
        student_profile = None
        audience = data.get("audience")

        if audience == "group":
            cohort_id = data.get("cohort_id")
            if not cohort_id:
                return Response({"detail": "cohort_id required for group audience"}, status=400)
            try:
                cohort = Cohort.objects.get(pk=cohort_id, course=course)
            except Cohort.DoesNotExist:
                return Response({"detail": "Cohort not found"}, status=404)

        elif audience == "individual":
            student_email = (data.get("student_email") or "").strip().lower()
            sp_id = data.get("student_profile_id")
            if student_email:
                try:
                    stu_user = User.objects.get(email__iexact=student_email, role=User.RoleChoices.STUDENT)
                    student_profile = stu_user.student_profile
                except User.DoesNotExist:
                    return Response({"detail": "No student with this email"}, status=404)
            elif sp_id:
                try:
                    student_profile = StudentProfile.objects.get(pk=sp_id)
                except StudentProfile.DoesNotExist:
                    return Response({"detail": "Student not found"}, status=404)
            else:
                return Response({"detail": "student_email or student_profile_id required for individual audience"}, status=400)

        try:
            session = Session.objects.create(
                course=course,
                cohort=cohort,
                student_profile=student_profile,
                date=data["date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                meeting_link=data.get("meeting_link") or None,
                lesson_id=data.get("lesson_id") or None,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        ScheduleNotificationService.notify_extra_session_created(session)
        return Response({"status": "created", "id": f"session_{session.id}"}, status=201)


# ── Invitations ────────────────────────────────────────────────────────────────

@extend_schema(tags=["Calendar"])
class EventInviteView(APIView):
    """POST /calendar/events/personal/{id}/invite/ — invite a user by email."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        try:
            ev = PersonalEvent.objects.get(pk=pk, owner=request.user)
        except PersonalEvent.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "email is required"}, status=400)

        try:
            invitee = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "No user with this email"}, status=404)

        if invitee == request.user:
            return Response({"detail": "Cannot invite yourself"}, status=400)

        inv, created = EventInvitation.objects.get_or_create(
            event=ev, invitee=invitee,
            defaults={"status": EventInvitation.Status.PENDING},
        )
        if not created and inv.status == EventInvitation.Status.DECLINED:
            inv.status = EventInvitation.Status.PENDING
            inv.responded_at = None
            inv.save()

        ScheduleNotificationService.notify_event_invited(inv, actor=request.user)
        return Response({"status": "invited", "invitation_id": inv.id}, status=201 if created else 200)


@extend_schema(tags=["Calendar"])
class InvitationListView(APIView):
    """GET /calendar/invitations/ — pending + declined invitations for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        EventInvitation.objects.filter(
            invitee=request.user,
            status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.DECLINED],
        ).filter(
            Q(event__date__lt=today) |
            Q(event__date=today, event__end_time__lte=current_time)
        ).delete()

        invitations = (
            EventInvitation.objects
            .filter(
                invitee=request.user,
                status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.DECLINED],
            )
            .select_related("event__owner")
            .order_by("event__date", "event__start_time")
        )

        user = request.user
        data = [
            {
                "id":        inv.id,
                "status":    inv.status,
                "conflicts": _check_personal_event_conflicts(
                    user, inv.event.date, inv.event.start_time, inv.event.end_time,
                ),
                "event": {
                    "id":           f"personal_{inv.event_id}",
                    "title":        inv.event.title,
                    "date":         inv.event.date.isoformat(),
                    "start_time":   _fmt(inv.event.start_time),
                    "end_time":     _fmt(inv.event.end_time),
                    "meeting_link": inv.event.meeting_link,
                    "organizer":    inv.event.owner.get_full_name() or inv.event.owner.email,
                },
            }
            for inv in invitations
        ]
        return Response(data)


@extend_schema(tags=["Calendar"])
class InvitationRespondView(APIView):
    """PATCH /calendar/invitations/{id}/ — accept or decline."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        try:
            inv = EventInvitation.objects.select_related("event").get(pk=pk, invitee=request.user)
        except EventInvitation.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        event_end = datetime.combine(inv.event.date, inv.event.end_time)
        if timezone.now() > timezone.make_aware(event_end):
            return Response({"detail": "Event has already ended"}, status=400)

        action = request.data.get("action")
        if action not in ("accept", "decline"):
            return Response({"detail": "action must be accept or decline"}, status=400)

        if action == "accept":
            conflicts = _check_personal_event_conflicts(
                request.user,
                inv.event.date,
                inv.event.start_time,
                inv.event.end_time,
            )
            if conflicts:
                return Response(
                    {"detail": "You have a schedule conflict at this time.", "conflicts": conflicts},
                    status=409,
                )

        inv.status = (
            EventInvitation.Status.ACCEPTED
            if action == "accept"
            else EventInvitation.Status.DECLINED
        )
        inv.responded_at = timezone.now()
        inv.save()
        ScheduleNotificationService.notify_invitation_responded(inv)
        return Response({"status": inv.status})


@extend_schema(tags=["Calendar"])
class EventInvitationStatusView(APIView):
    """GET /calendar/events/personal/{id}/invitations/ — list for event organizer."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        try:
            ev = PersonalEvent.objects.get(pk=pk, owner=request.user)
        except PersonalEvent.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        invitations = ev.invitations.select_related("invitee").order_by("created_at")
        data = [
            {
                "id":      inv.id,
                "email":   inv.invitee.email,
                "name":    inv.invitee.get_full_name() or inv.invitee.email,
                "avatar":  request.build_absolute_uri(inv.invitee.avatar.url) if inv.invitee.avatar else None,
                "status":  inv.status,
                "responded_at": inv.responded_at.isoformat() if inv.responded_at else None,
            }
            for inv in invitations
        ]
        return Response(data)


@extend_schema(tags=["Calendar"])
class EventParticipantsView(APIView):
    """GET /calendar/events/personal/{id}/participants/ — accessible to owner and any invitee."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        user = request.user
        my_invite = None

        try:
            ev = PersonalEvent.objects.get(pk=pk, owner=user)
            is_owner = True
        except PersonalEvent.DoesNotExist:
            is_owner = False
            try:
                inv_self = EventInvitation.objects.select_related("event").get(
                    event_id=pk, invitee=user,
                )
                ev = inv_self.event
                my_invite = {
                    "status":       inv_self.status,
                    "invited_at":   inv_self.created_at.isoformat(),
                    "responded_at": inv_self.responded_at.isoformat() if inv_self.responded_at else None,
                }
            except EventInvitation.DoesNotExist:
                return Response({"detail": "Not found"}, status=404)

        invitations = ev.invitations.select_related("invitee").order_by("created_at")

        def _avatar(u):
            return request.build_absolute_uri(u.avatar.url) if u.avatar else None

        if is_owner:
            participants = [
                {
                    "name":         inv.invitee.get_full_name() or inv.invitee.email,
                    "email":        inv.invitee.email,
                    "avatar":       _avatar(inv.invitee),
                    "status":       inv.status,
                    "responded_at": inv.responded_at.isoformat() if inv.responded_at else None,
                }
                for inv in invitations
            ]
        else:
            participants = [
                {
                    "name":   inv.invitee.get_full_name() or inv.invitee.email,
                    "avatar": _avatar(inv.invitee),
                    "status": inv.status,
                }
                for inv in invitations
                if inv.invitee_id != user.id
            ]

        return Response({"my_invite": my_invite, "participants": participants})


# ── Session / Calendar Event update ───────────────────────────────────────────

@extend_schema(tags=["Calendar"])
class CalendarEventUpdateView(APIView):
    """
    PATCH /calendar/events/{event_id}/
    event_id formats:
      session_{id}  — update a Session (cancel / reschedule / update_link / update_lesson)
      personal_{id} — handled by PersonalEventDetailView
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, event_id: str):
        data   = request.data
        action = data.get("action")
        if action not in ("cancel", "reschedule", "restore", "update_link", "update_lesson"):
            return Response({"detail": "action must be cancel, reschedule, restore, update_link, or update_lesson"}, status=400)

        session = self._resolve_session(event_id, request.user)
        if session is None:
            return Response({"detail": "Session not found or not owned by you"}, status=404)

        if action == "update_link":
            session.meeting_link = data.get("meeting_link") or None
            session.save()
            return Response({"status": "ok"})

        if action == "update_lesson":
            lesson_id = data.get("lesson_id")
            if lesson_id is not None:
                try:
                    lesson_id = int(lesson_id)
                except (ValueError, TypeError):
                    return Response({"detail": "Invalid lesson_id"}, status=400)
            session.lesson_id = lesson_id
            session.save()
            return Response({"status": "ok"})

        if action == "cancel":
            ScheduleNotificationService.notify_session_cancelled(session, actor=request.user)
            if session.rescheduled_from_date:
                Session.objects.filter(
                    date=session.rescheduled_from_date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                    status=Session.Status.RESCHEDULED,
                ).update(status=Session.Status.CANCELLED, rescheduled_to_date=None)
                session.delete()
            else:
                session.status = Session.Status.CANCELLED
                session.save()
            return Response({"status": "ok"})

        if action == "restore":
            if session.rescheduled_from_date:
                original = Session.objects.filter(
                    date=session.rescheduled_from_date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                    status=Session.Status.RESCHEDULED,
                ).first()
                if original is None:
                    return Response({"detail": "Original session not found."}, status=404)
                conflict_qs = Session.objects.filter(
                    date=original.date,
                    status=Session.Status.SCHEDULED,
                    rescheduled_from_date__isnull=True,
                ).exclude(pk=original.pk)
                if original.slot_id:
                    conflict_qs = conflict_qs.filter(slot=original.slot)
                elif original.schedule_id:
                    conflict_qs = conflict_qs.filter(schedule=original.schedule)
                else:
                    conflict_qs = conflict_qs.filter(course=original.course)
                if conflict_qs.exists():
                    return Response({"detail": "Another session already occupies the original slot."}, status=409)
                original.status = Session.Status.SCHEDULED
                original.rescheduled_to_date = None
                original.save()
                session.delete()
                ScheduleNotificationService.notify_session_restored(original, actor=request.user)
                return Response({"status": "ok"})

            if session.status not in (Session.Status.CANCELLED, Session.Status.RESCHEDULED):
                return Response({"detail": "Session is not cancelled or rescheduled."}, status=400)

            conflict_qs = Session.objects.filter(
                date=session.date,
                status=Session.Status.SCHEDULED,
                rescheduled_from_date__isnull=True,
            ).exclude(pk=session.pk)
            if session.slot_id:
                conflict_qs = conflict_qs.filter(slot=session.slot)
            elif session.schedule_id:
                conflict_qs = conflict_qs.filter(schedule=session.schedule)
            else:
                conflict_qs = conflict_qs.filter(course=session.course)
            if conflict_qs.exists():
                return Response({"detail": "Another session is already scheduled at this slot and date."}, status=409)

            if session.slot_id:
                teacher = session.slot.delivery_format.course.teacher_profile
            elif session.schedule_id:
                teacher = session.schedule.cohort.course.teacher_profile
            else:
                teacher = session.course.teacher_profile

            time_overlap = Q(start_time__lt=session.end_time) & Q(end_time__gt=session.start_time)
            unavail_exists = TeacherUnavailability.objects.filter(
                time_overlap,
                teacher_profile=teacher,
            ).filter(
                Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.WEEKLY,
                    day_of_week=session.date.weekday(),
                ) | Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.ONE_TIME,
                    date=session.date,
                ) | Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.DATE_RANGE,
                    date__lte=session.date,
                    date_to__gte=session.date,
                )
            ).exists()
            if unavail_exists:
                return Response({"detail": "Teacher is marked unavailable at this time."}, status=409)

            if session.status == Session.Status.RESCHEDULED:
                Session.objects.filter(
                    rescheduled_from_date=session.date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                ).exclude(status=Session.Status.CANCELLED).delete()

            session.status = Session.Status.SCHEDULED
            session.rescheduled_to_date = None
            session.save()
            ScheduleNotificationService.notify_session_restored(session, actor=request.user)
            return Response({"status": "ok"})

        if action == "reschedule":
            nd, ns, ne = data.get("new_date"), data.get("new_start_time"), data.get("new_end_time")
            if not nd or not ns or not ne:
                return Response({"detail": "new_date, new_start_time, new_end_time are required"}, status=400)
            try:
                new_date = date.fromisoformat(nd)
            except ValueError:
                return Response({"detail": "Invalid new_date"}, status=400)

            new_link = data.get("meeting_link")

            if session.slot_id:
                teacher = session.slot.delivery_format.course.teacher_profile
            elif session.schedule_id:
                teacher = session.schedule.cohort.course.teacher_profile
            else:
                teacher = session.course.teacher_profile

            time_overlap = Q(start_time__lt=ne) & Q(end_time__gt=ns)

            session_conflict_qs = Session.objects.filter(
                time_overlap,
                date=new_date,
                status=Session.Status.SCHEDULED,
            ).filter(
                Q(slot__delivery_format__course__teacher_profile=teacher) |
                Q(schedule__cohort__course__teacher_profile=teacher) |
                Q(course__teacher_profile=teacher)
            ).exclude(pk=session.pk)

            if session.rescheduled_to_date:
                existing_repl = Session.objects.filter(
                    rescheduled_from_date=session.date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                ).exclude(status=Session.Status.CANCELLED).first()
                if existing_repl:
                    session_conflict_qs = session_conflict_qs.exclude(pk=existing_repl.pk)

            if session_conflict_qs.exists():
                return Response({"detail": "New time conflicts with an existing session."}, status=409)

            if PersonalEvent.objects.filter(time_overlap, date=new_date, owner=teacher.user).exists():
                return Response({"detail": "New time conflicts with a personal event."}, status=409)

            if TeacherUnavailability.objects.filter(
                time_overlap,
                teacher_profile=teacher,
            ).filter(
                Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.WEEKLY,
                    day_of_week=new_date.weekday(),
                ) | Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.ONE_TIME,
                    date=new_date,
                ) | Q(
                    recurrence_type=TeacherUnavailability.RecurrenceType.DATE_RANGE,
                    date__lte=new_date,
                    date_to__gte=new_date,
                )
            ).exists():
                return Response({"detail": "Teacher is unavailable at the new time."}, status=409)

            if session.rescheduled_from_date:
                old_date, old_start, old_end = session.date, session.start_time, session.end_time
                original_date = session.rescheduled_from_date
                session.date        = new_date
                session.start_time  = ns
                session.end_time    = ne
                session.meeting_link = new_link or session.meeting_link
                session.save()
                Session.objects.filter(
                    date=original_date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                    status=Session.Status.RESCHEDULED,
                ).update(rescheduled_to_date=new_date)
                ScheduleNotificationService.notify_session_rescheduled(
                    session, actor=request.user, old_date=old_date, old_start_time=old_start, old_end_time=old_end,
                )
                return Response({"status": "ok", "replacement_session_id": session.id})

            if session.rescheduled_to_date:
                replacement = Session.objects.filter(
                    rescheduled_from_date=session.date,
                    slot=session.slot,
                    schedule=session.schedule,
                    course=session.course,
                ).exclude(status=Session.Status.CANCELLED).first()
                if replacement:
                    old_date, old_start, old_end = replacement.date, replacement.start_time, replacement.end_time
                    replacement.date        = new_date
                    replacement.start_time  = ns
                    replacement.end_time    = ne
                    replacement.meeting_link = new_link or replacement.meeting_link
                    replacement.save()
                    session.rescheduled_to_date = new_date
                    session.save()
                    ScheduleNotificationService.notify_session_rescheduled(
                        replacement, actor=request.user, old_date=old_date, old_start_time=old_start, old_end_time=old_end,
                    )
                    return Response({"status": "ok", "replacement_session_id": replacement.id})

            original_date = session.date
            old_start, old_end = session.start_time, session.end_time
            session.status              = Session.Status.RESCHEDULED
            session.rescheduled_to_date = new_date
            session.save()
            replacement = Session.objects.create(
                slot=session.slot,
                schedule=session.schedule,
                course=session.course,
                cohort=session.cohort,
                student_profile=session.student_profile,
                date=new_date,
                start_time=ns,
                end_time=ne,
                meeting_link=new_link or session.meeting_link,
                lesson=session.lesson,
                rescheduled_from_date=original_date,
            )
            ScheduleNotificationService.notify_session_rescheduled(
                replacement, actor=request.user, old_date=original_date, old_start_time=old_start, old_end_time=old_end,
            )
            return Response({"status": "ok", "replacement_session_id": replacement.id})

        return Response(status=400)

    def _resolve_session(self, event_id: str, user) -> Session | None:
        if not event_id.startswith("session_"):
            return None
        try:
            session_id = int(event_id[8:])
        except (ValueError, TypeError):
            return None

        try:
            session = Session.objects.select_related(
                "slot__delivery_format__course__teacher_profile",
                "schedule__cohort__course__teacher_profile",
                "course__teacher_profile",
            ).get(pk=session_id)
        except Session.DoesNotExist:
            return None

        if session.slot_id:
            if session.slot.delivery_format.course.teacher_profile != user.teacher_profile:
                return None
        elif session.schedule_id:
            if session.schedule.cohort.course.teacher_profile != user.teacher_profile:
                return None
        elif session.course_id:
            if session.course.teacher_profile != user.teacher_profile:
                return None
        else:
            return None

        return session