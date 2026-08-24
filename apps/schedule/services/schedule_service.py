from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q

from apps.courses.models import Cohort, CourseDeliveryFormat
from apps.schedule.exceptions import (
    InvalidScheduleTimeError,
    SlotAlreadyBookedError,
    TeacherScheduleConflictError,
)
from apps.schedule.models import (
    CohortSchedule,
    EventInvitation,
    PersonalEvent,
    ScheduleOverride,
    ScheduleSlot,
    Session,
    TeacherUnavailability,
)
from apps.users.models import TeacherProfile


class ScheduleService:
    @staticmethod
    def _time_overlap_filter(start_time, end_time) -> Q:
        return Q(start_time__lt=end_time) & Q(end_time__gt=start_time)

    @classmethod
    def _check_teacher_conflict(
        cls,
        teacher_profile: TeacherProfile,
        day_of_week: int,
        start_time,
        end_time,
        *,
        exclude_slot_id: int | None = None,
        exclude_cohort_schedule_id: int | None = None,
        exclude_unavailability_id: int | None = None,
        specific_date=None,
        ignore_unavailability: bool = False,
    ) -> None:
        overlap = cls._time_overlap_filter(start_time, end_time)
        day_q = Q(day_of_week=day_of_week)

        inactive_override = [ScheduleOverride.Status.CANCELLED, ScheduleOverride.Status.RESCHEDULED]
        inactive_session = [Session.Status.CANCELLED, Session.Status.RESCHEDULED]

        slot_qs = ScheduleSlot.objects.filter(
            day_q & overlap,
            delivery_format__course__teacher_profile=teacher_profile,
        )
        if exclude_slot_id:
            slot_qs = slot_qs.exclude(pk=exclude_slot_id)
        if slot_qs.exists():
            if specific_date is None:
                raise TeacherScheduleConflictError(
                    "Teacher already has an individual session at this day and time."
                )
            for slot in slot_qs:
                already_handled = (
                    ScheduleOverride.objects.filter(
                        slot=slot,
                        original_date=specific_date,
                        status__in=inactive_override,
                    ).exists()
                    or Session.objects.filter(
                        slot=slot,
                        date=specific_date,
                        status__in=inactive_session,
                    ).exists()
                )
                if not already_handled:
                    raise TeacherScheduleConflictError(
                        "Teacher already has an individual session at this day and time."
                    )

        cohort_qs = CohortSchedule.objects.filter(
            day_q & overlap,
            cohort__course__teacher_profile=teacher_profile,
        )
        if exclude_cohort_schedule_id:
            cohort_qs = cohort_qs.exclude(pk=exclude_cohort_schedule_id)
        if cohort_qs.exists():
            if specific_date is None:
                raise TeacherScheduleConflictError(
                    "Teacher already has a group session at this day and time."
                )
            for schedule in cohort_qs:
                already_handled = (
                    ScheduleOverride.objects.filter(
                        schedule=schedule,
                        original_date=specific_date,
                        status__in=inactive_override,
                    ).exists()
                    or Session.objects.filter(
                        schedule=schedule,
                        date=specific_date,
                        status__in=inactive_session,
                    ).exists()
                )
                if not already_handled:
                    raise TeacherScheduleConflictError(
                        "Teacher already has a group session at this day and time."
                    )

        if not ignore_unavailability:
            unavail_qs = TeacherUnavailability.objects.filter(
                day_q & overlap,
                teacher_profile=teacher_profile,
            )
            if exclude_unavailability_id:
                unavail_qs = unavail_qs.exclude(pk=exclude_unavailability_id)
            if unavail_qs.exists():
                raise TeacherScheduleConflictError(
                    "Teacher has a personal unavailability block at this day and time."
                )

    @staticmethod
    def _validate_time_range(start_time, end_time) -> None:
        if end_time <= start_time:
            raise InvalidScheduleTimeError("end_time must be after start_time.")

    @classmethod
    def _collect_onetime_unavailability_dates(
        cls,
        teacher_profile: TeacherProfile,
        day_of_week: int,
        start_time,
        end_time,
    ) -> list:
        overlap = cls._time_overlap_filter(start_time, end_time)
        unavails = TeacherUnavailability.objects.filter(
            teacher_profile=teacher_profile,
            day_of_week=day_of_week,
            recurrence_type__in=[
                TeacherUnavailability.RecurrenceType.ONE_TIME,
                TeacherUnavailability.RecurrenceType.DATE_RANGE,
            ],
        ).filter(overlap)

        dates = []
        for u in unavails:
            if u.recurrence_type == TeacherUnavailability.RecurrenceType.ONE_TIME:
                dates.append(u.date)
            else:
                d = u.date
                while d <= u.date_to:
                    if d.weekday() == day_of_week:
                        dates.append(d)
                    d += timedelta(days=1)
        return dates

    @classmethod
    def get_schedule_conflicts(
        cls,
        teacher_profile: TeacherProfile,
        day_of_week: int,
        start_time,
        end_time,
        exclude_cohort_schedule_id: int | None = None,
        exclude_slot_id: int | None = None,
        cohort_start_date=None,
        cohort_duration_months: int | None = None,
    ) -> dict:
        import calendar as _cal
        from datetime import date as _date
        from datetime import timedelta

        overlap = cls._time_overlap_filter(start_time, end_time)
        day_q = Q(day_of_week=day_of_week)
        result: dict = {"group": [], "individual": [], "personal": [], "personal_events": []}

        slot_qs = ScheduleSlot.objects.filter(
            day_q & overlap,
            delivery_format__course__teacher_profile=teacher_profile,
        ).select_related("delivery_format__course")
        if exclude_slot_id:
            slot_qs = slot_qs.exclude(pk=exclude_slot_id)
        for slot in slot_qs:
            result["individual"].append(
                {
                    "id": slot.id,
                    "course_title": slot.delivery_format.course.title,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                }
            )

        cohort_qs = CohortSchedule.objects.filter(
            day_q & overlap,
            cohort__course__teacher_profile=teacher_profile,
        ).select_related("cohort__course", "cohort")
        if exclude_cohort_schedule_id:
            cohort_qs = cohort_qs.exclude(pk=exclude_cohort_schedule_id)
        for sched in cohort_qs:
            result["group"].append(
                {
                    "id": sched.id,
                    "course_title": sched.cohort.course.title,
                    "cohort_name": sched.cohort.name,
                    "start_time": sched.start_time.strftime("%H:%M"),
                    "end_time": sched.end_time.strftime("%H:%M"),
                }
            )

        for u in TeacherUnavailability.objects.filter(
            day_q & overlap,
            teacher_profile=teacher_profile,
            recurrence_type=TeacherUnavailability.RecurrenceType.WEEKLY,
        ):
            result["personal"].append(
                {
                    "id": u.id,
                    "reason": u.reason,
                    "start_time": u.start_time.strftime("%H:%M"),
                    "end_time": u.end_time.strftime("%H:%M"),
                }
            )

        today = _date.today()
        date_from = max(cohort_start_date, today) if cohort_start_date else today
        if cohort_start_date and cohort_duration_months:
            m = cohort_start_date.month - 1 + cohort_duration_months
            date_to = _date(
                cohort_start_date.year + m // 12,
                m % 12 + 1,
                min(
                    cohort_start_date.day,
                    _cal.monthrange(cohort_start_date.year + m // 12, m % 12 + 1)[1],
                ),
            )
        else:
            date_to = today + timedelta(days=365)

        iso_dow = day_of_week + 1
        user = teacher_profile.user
        event_overlap = Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
        date_range = Q(date__gte=date_from) & Q(date__lte=date_to) & Q(date__iso_week_day=iso_dow)

        seen_event_ids: set[int] = set()

        for event in PersonalEvent.objects.filter(event_overlap & date_range, owner=user):
            seen_event_ids.add(event.id)
            result["personal_events"].append(
                {
                    "id": event.id,
                    "title": event.title,
                    "date": event.date.isoformat(),
                    "start_time": event.start_time.strftime("%H:%M"),
                    "end_time": event.end_time.strftime("%H:%M"),
                    "is_owner": True,
                    "invitation_id": None,
                }
            )

        inv_event_overlap = Q(event__start_time__lt=end_time) & Q(event__end_time__gt=start_time)
        inv_date_range = (
            Q(event__date__gte=date_from)
            & Q(event__date__lte=date_to)
            & Q(event__date__iso_week_day=iso_dow)
        )
        for inv in EventInvitation.objects.filter(
            inv_event_overlap & inv_date_range,
            invitee=user,
            status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.ACCEPTED],
        ).select_related("event"):
            ev = inv.event
            if ev.id in seen_event_ids:
                continue
            result["personal_events"].append(
                {
                    "id": ev.id,
                    "title": ev.title,
                    "date": ev.date.isoformat(),
                    "start_time": ev.start_time.strftime("%H:%M"),
                    "end_time": ev.end_time.strftime("%H:%M"),
                    "is_owner": False,
                    "invitation_id": inv.id,
                }
            )

        return result

    @classmethod
    @transaction.atomic
    def create_schedule_slot(
        cls,
        delivery_format: CourseDeliveryFormat,
        validated_data: dict,
    ) -> ScheduleSlot:
        day = validated_data["day_of_week"]
        start = validated_data["start_time"]
        end = validated_data["end_time"]
        teacher = delivery_format.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(teacher, day, start, end, ignore_unavailability=True)

        slot = ScheduleSlot.objects.create(
            delivery_format=delivery_format,
            day_of_week=day,
            start_time=start,
            end_time=end,
        )

        for conflict_date in cls._collect_onetime_unavailability_dates(teacher, day, start, end):
            Session.objects.get_or_create(
                slot=slot,
                date=conflict_date,
                rescheduled_from_date=None,
                defaults={"start_time": start, "end_time": end, "status": Session.Status.CANCELLED},
            )

        return slot

    @classmethod
    @transaction.atomic
    def reschedule_slot(
        cls,
        slot: ScheduleSlot,
        validated_data: dict,
    ) -> ScheduleSlot:
        """Move an existing slot to a new day/time (reschedule). Preserves original values."""
        day = validated_data.get("day_of_week", slot.day_of_week)
        start = validated_data.get("start_time", slot.start_time)
        end = validated_data.get("end_time", slot.end_time)
        teacher = slot.delivery_format.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(
            teacher, day, start, end, exclude_slot_id=slot.pk, ignore_unavailability=True
        )

        if slot.booked_by_id:
            iso_dow = day + 1
            overlap = cls._time_overlap_filter(start, end)
            date_dow = Q(date__iso_week_day=iso_dow)
            user = teacher.user
            if PersonalEvent.objects.filter(overlap & date_dow, owner=user).exists():
                raise TeacherScheduleConflictError(
                    "Teacher has a personal event on this weekday and time."
                )

        old_day = slot.day_of_week
        old_start = slot.start_time
        old_end = slot.end_time

        if slot.booked_by_id and not slot.is_rescheduled:
            slot.original_day_of_week = old_day
            slot.original_start_time = old_start
            slot.original_end_time = old_end
            slot.is_rescheduled = True

        slot.day_of_week = day
        slot.start_time = start
        slot.end_time = end
        slot.save()

        day_changed = old_day != day
        time_changed = old_start != start or old_end != end
        if day_changed or time_changed:
            today = date.today()
            future = Session.objects.filter(
                slot=slot,
                date__gte=today,
                status=Session.Status.SCHEDULED,
                rescheduled_from_date__isnull=True,
            )
            if day_changed:
                future.delete()
            else:
                future.update(start_time=start, end_time=end)

        return slot

    @staticmethod
    def book_slot(slot: ScheduleSlot, enrollment) -> ScheduleSlot:
        """Book a slot for an enrollment (called after successful payment)."""
        if not slot.is_available:
            raise SlotAlreadyBookedError("This slot has already been booked.")
        slot.booked_by = enrollment
        slot.save(update_fields=["booked_by"])
        return slot

    @staticmethod
    def release_slot(slot: ScheduleSlot) -> ScheduleSlot:
        """Release a slot back to available (e.g., on enrollment revocation)."""
        slot.booked_by = None
        slot.save(update_fields=["booked_by"])
        return slot

    @classmethod
    @transaction.atomic
    def create_cohort_schedule(
        cls,
        cohort: Cohort,
        validated_data: dict,
    ) -> CohortSchedule:
        day = validated_data["day_of_week"]
        start = validated_data["start_time"]
        end = validated_data["end_time"]
        teacher = cohort.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(teacher, day, start, end, ignore_unavailability=True)

        sched = CohortSchedule.objects.create(
            cohort=cohort,
            day_of_week=day,
            start_time=start,
            end_time=end,
        )

        for conflict_date in cls._collect_onetime_unavailability_dates(teacher, day, start, end):
            Session.objects.get_or_create(
                schedule=sched,
                date=conflict_date,
                rescheduled_from_date=None,
                defaults={"start_time": start, "end_time": end, "status": Session.Status.CANCELLED},
            )

        return sched

    @classmethod
    @transaction.atomic
    def update_cohort_schedule(
        cls,
        cohort_schedule: CohortSchedule,
        validated_data: dict,
    ) -> CohortSchedule:
        day = validated_data.get("day_of_week", cohort_schedule.day_of_week)
        start = validated_data.get("start_time", cohort_schedule.start_time)
        end = validated_data.get("end_time", cohort_schedule.end_time)
        teacher = cohort_schedule.cohort.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(
            teacher,
            day,
            start,
            end,
            exclude_cohort_schedule_id=cohort_schedule.pk,
            ignore_unavailability=True,
        )

        cohort_schedule.day_of_week = day
        cohort_schedule.start_time = start
        cohort_schedule.end_time = end
        cohort_schedule.save()
        return cohort_schedule

    @classmethod
    @transaction.atomic
    def create_unavailability(
        cls,
        teacher_profile: TeacherProfile,
        validated_data: dict,
    ) -> TeacherUnavailability:
        recurrence = validated_data["recurrence_type"]
        date = validated_data.get("date")
        date_to = validated_data.get("date_to")
        start = validated_data["start_time"]
        end = validated_data["end_time"]

        cls._validate_time_range(start, end)

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            day = date.weekday()
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            day = date.weekday()
        else:
            day = validated_data["day_of_week"]
            date = None
            date_to = None

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            cls._check_teacher_conflict(teacher_profile, day, start, end, specific_date=date)
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            from datetime import timedelta as _td

            seen_weekdays: set[int] = set()
            d = validated_data["date"]
            d_to = validated_data["date_to"]
            cur = d
            while cur <= d_to:
                wd = cur.weekday()
                if wd not in seen_weekdays:
                    seen_weekdays.add(wd)
                    cls._check_teacher_conflict(teacher_profile, wd, start, end, specific_date=None)
                    if len(seen_weekdays) == 7:
                        break
                cur += _td(days=1)
        else:
            cls._check_teacher_conflict(teacher_profile, day, start, end)

        return TeacherUnavailability.objects.create(
            teacher_profile=teacher_profile,
            recurrence_type=recurrence,
            day_of_week=day,
            date=date,
            date_to=date_to,
            start_time=start,
            end_time=end,
            reason=validated_data.get("reason", ""),
        )

    @classmethod
    @transaction.atomic
    def update_unavailability(
        cls,
        unavailability: TeacherUnavailability,
        validated_data: dict,
    ) -> TeacherUnavailability:
        recurrence = validated_data.get("recurrence_type", unavailability.recurrence_type)
        date = validated_data.get("date", unavailability.date)
        date_to = validated_data.get("date_to", unavailability.date_to)
        start = validated_data.get("start_time", unavailability.start_time)
        end = validated_data.get("end_time", unavailability.end_time)

        cls._validate_time_range(start, end)

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            day = date.weekday()
            date_to = None
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            day = date.weekday()
        else:
            day = validated_data.get("day_of_week", unavailability.day_of_week)
            date = None
            date_to = None

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            cls._check_teacher_conflict(
                unavailability.teacher_profile,
                day,
                start,
                end,
                exclude_unavailability_id=unavailability.pk,
                specific_date=date,
            )
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            from datetime import timedelta as _td

            seen_weekdays: set[int] = set()
            cur = date
            d_to = date_to
            while cur <= d_to:
                wd = cur.weekday()
                if wd not in seen_weekdays:
                    seen_weekdays.add(wd)
                    cls._check_teacher_conflict(
                        unavailability.teacher_profile,
                        wd,
                        start,
                        end,
                        exclude_unavailability_id=unavailability.pk,
                    )
                    if len(seen_weekdays) == 7:
                        break
                cur += _td(days=1)
        else:
            cls._check_teacher_conflict(
                unavailability.teacher_profile,
                day,
                start,
                end,
                exclude_unavailability_id=unavailability.pk,
            )

        unavailability.recurrence_type = recurrence
        unavailability.day_of_week = day
        unavailability.date = date
        unavailability.date_to = date_to
        unavailability.start_time = start
        unavailability.end_time = end
        unavailability.reason = validated_data.get("reason", unavailability.reason)
        unavailability.save()
        return unavailability

    @staticmethod
    def get_available_slots(delivery_format: CourseDeliveryFormat):
        """Return only unbooked slots, shown to prospective buyers."""
        return ScheduleSlot.objects.filter(
            delivery_format=delivery_format,
            booked_by__isnull=True,
        )

    @staticmethod
    def get_all_slots(delivery_format: CourseDeliveryFormat):
        """Return all slots (teacher view)."""
        return ScheduleSlot.objects.filter(delivery_format=delivery_format)
