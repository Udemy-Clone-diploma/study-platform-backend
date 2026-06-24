from django.db import transaction
from django.db.models import Q

from apps.courses.exceptions import (
    InvalidScheduleTimeError,
    SlotAlreadyBookedError,
    SlotNotAvailableError,
    TeacherScheduleConflictError,
)
from apps.courses.models import (
    Cohort,
    CohortSchedule,
    CourseDeliveryFormat,
    ScheduleSlot,
    TeacherUnavailability,
)
from apps.users.models import TeacherProfile


class ScheduleService:
    """
    Handles creation, update, and deletion of schedule entities:
      - ScheduleSlot (individual delivery format)
      - CohortSchedule (group cohort)
      - TeacherUnavailability (personal blocks)

    All write operations validate that the teacher has no conflicting sessions
    at the requested day + time window.
    """

    # ── Conflict checker ───────────────────────────────────────────────

    @staticmethod
    def _time_overlap_filter(start_time, end_time) -> Q:
        """
        Returns a Q filter that matches any row whose [start, end) overlaps [start_time, end_time).
        Two intervals overlap when one starts before the other ends.
        """
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
    ) -> None:
        """
        Raises TeacherScheduleConflictError if the teacher already has ANY session
        (ScheduleSlot, CohortSchedule, or TeacherUnavailability) on the given
        day_of_week that overlaps [start_time, end_time).

        exclude_* args allow skipping the row being updated.
        """
        overlap = cls._time_overlap_filter(start_time, end_time)
        day_q = Q(day_of_week=day_of_week)

        # --- Individual ScheduleSlots across all courses of this teacher ---
        slot_qs = ScheduleSlot.objects.filter(
            day_q & overlap,
            delivery_format__course__teacher_profile=teacher_profile,
        )
        if exclude_slot_id:
            slot_qs = slot_qs.exclude(pk=exclude_slot_id)
        if slot_qs.exists():
            raise TeacherScheduleConflictError(
                "Teacher already has an individual session at this day and time."
            )

        # --- CohortSchedules across all group cohorts of this teacher ---
        cohort_qs = CohortSchedule.objects.filter(
            day_q & overlap,
            cohort__course__teacher_profile=teacher_profile,
        )
        if exclude_cohort_schedule_id:
            cohort_qs = cohort_qs.exclude(pk=exclude_cohort_schedule_id)
        if cohort_qs.exists():
            raise TeacherScheduleConflictError(
                "Teacher already has a group session at this day and time."
            )

        # --- TeacherUnavailability blocks ---
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

    # ── ScheduleSlot (individual) ──────────────────────────────────────

    @classmethod
    @transaction.atomic
    def create_schedule_slot(
        cls,
        delivery_format: CourseDeliveryFormat,
        validated_data: dict,
    ) -> ScheduleSlot:
        day      = validated_data["day_of_week"]
        start    = validated_data["start_time"]
        end      = validated_data["end_time"]
        teacher  = delivery_format.course.teacher_profile

        cls._validate_time_range(start, end)

        cls._check_teacher_conflict(teacher, day, start, end)

        return ScheduleSlot.objects.create(
            delivery_format=delivery_format,
            day_of_week=day,
            start_time=start,
            end_time=end,
        )

    @classmethod
    @transaction.atomic
    def reschedule_slot(
        cls,
        slot: ScheduleSlot,
        validated_data: dict,
    ) -> ScheduleSlot:
        """Move an existing slot to a new day/time (reschedule). Preserves original values."""
        day   = validated_data.get("day_of_week", slot.day_of_week)
        start = validated_data.get("start_time",  slot.start_time)
        end   = validated_data.get("end_time",    slot.end_time)
        teacher = slot.delivery_format.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(teacher, day, start, end, exclude_slot_id=slot.pk)

        # Preserve original values on first reschedule.
        if not slot.is_rescheduled:
            slot.original_day_of_week = slot.day_of_week
            slot.original_start_time  = slot.start_time
            slot.original_end_time    = slot.end_time
            slot.is_rescheduled       = True

        slot.day_of_week = day
        slot.start_time  = start
        slot.end_time    = end
        slot.save()
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

    # ── CohortSchedule (group) ─────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def create_cohort_schedule(
        cls,
        cohort: Cohort,
        validated_data: dict,
    ) -> CohortSchedule:
        day     = validated_data["day_of_week"]
        start   = validated_data["start_time"]
        end     = validated_data["end_time"]
        teacher = cohort.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(teacher, day, start, end)

        return CohortSchedule.objects.create(
            cohort=cohort,
            day_of_week=day,
            start_time=start,
            end_time=end,
        )

    @classmethod
    @transaction.atomic
    def update_cohort_schedule(
        cls,
        cohort_schedule: CohortSchedule,
        validated_data: dict,
    ) -> CohortSchedule:
        day   = validated_data.get("day_of_week", cohort_schedule.day_of_week)
        start = validated_data.get("start_time",  cohort_schedule.start_time)
        end   = validated_data.get("end_time",    cohort_schedule.end_time)
        teacher = cohort_schedule.cohort.course.teacher_profile

        cls._validate_time_range(start, end)
        cls._check_teacher_conflict(
            teacher, day, start, end,
            exclude_cohort_schedule_id=cohort_schedule.pk,
        )

        cohort_schedule.day_of_week = day
        cohort_schedule.start_time  = start
        cohort_schedule.end_time    = end
        cohort_schedule.save()
        return cohort_schedule

    # ── TeacherUnavailability ──────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def create_unavailability(
        cls,
        teacher_profile: TeacherProfile,
        validated_data: dict,
    ) -> TeacherUnavailability:
        recurrence = validated_data["recurrence_type"]
        date       = validated_data.get("date")
        date_to    = validated_data.get("date_to")
        start      = validated_data["start_time"]
        end        = validated_data["end_time"]

        cls._validate_time_range(start, end)

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            day = date.weekday()
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            # Use 0 (Monday) as a placeholder; the date range itself is the authority.
            day = date.weekday()
        else:
            day = validated_data["day_of_week"]
            date = None
            date_to = None

        # Skip conflict check for date_range (the teacher intentionally blocks a span).
        if recurrence != TeacherUnavailability.RecurrenceType.DATE_RANGE:
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
        date       = validated_data.get("date", unavailability.date)
        date_to    = validated_data.get("date_to", unavailability.date_to)
        start      = validated_data.get("start_time", unavailability.start_time)
        end        = validated_data.get("end_time",   unavailability.end_time)

        cls._validate_time_range(start, end)

        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            day = date.weekday()
            date_to = None
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            day = date.weekday()
        else:
            day     = validated_data.get("day_of_week", unavailability.day_of_week)
            date    = None
            date_to = None

        if recurrence != TeacherUnavailability.RecurrenceType.DATE_RANGE:
            cls._check_teacher_conflict(
                unavailability.teacher_profile, day, start, end,
                exclude_unavailability_id=unavailability.pk,
            )

        unavailability.recurrence_type = recurrence
        unavailability.day_of_week     = day
        unavailability.date            = date
        unavailability.date_to         = date_to
        unavailability.start_time      = start
        unavailability.end_time        = end
        unavailability.reason          = validated_data.get("reason", unavailability.reason)
        unavailability.save()
        return unavailability

    # ── Read helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_available_slots(delivery_format: CourseDeliveryFormat):
        """Return only unbooked slots — shown to prospective buyers."""
        return ScheduleSlot.objects.filter(
            delivery_format=delivery_format,
            booked_by__isnull=True,
        )

    @staticmethod
    def get_all_slots(delivery_format: CourseDeliveryFormat):
        """Return all slots (teacher view)."""
        return ScheduleSlot.objects.filter(delivery_format=delivery_format)
