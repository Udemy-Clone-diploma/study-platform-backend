from datetime import date

from django.db import models

from .CourseDeliveryFormat import CourseDeliveryFormat


class ScheduleSlot(models.Model):
    """
    A recurring weekly time slot offered by a teacher for an individual delivery format.

    Teacher manually creates these slots to define when they are available.
    Each slot can be booked by one student at a time (booked_by set to their Enrollment).
    Unbooked slots (booked_by=None) are visible to prospective buyers.

    A slot can be rescheduled: teacher updates day/time; original values are preserved
    so both parties can see what changed.
    """

    class DayOfWeek(models.IntegerChoices):
        MONDAY    = 0, "Monday"
        TUESDAY   = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY  = 3, "Thursday"
        FRIDAY    = 4, "Friday"
        SATURDAY  = 5, "Saturday"
        SUNDAY    = 6, "Sunday"

    delivery_format = models.ForeignKey(
        CourseDeliveryFormat,
        on_delete=models.CASCADE,
        related_name="schedule_slots",
        limit_choices_to={"format_type": CourseDeliveryFormat.FormatType.INDIVIDUAL},
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    start_time  = models.TimeField()
    end_time    = models.TimeField()

    # Set when a student books this slot (via enrollment after purchase).
    # None = slot is still available for purchase.
    booked_by = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_slots",
    )

    # Original time preserved when slot is rescheduled so teacher/student can see the change.
    original_day_of_week = models.PositiveSmallIntegerField(
        choices=DayOfWeek.choices, null=True, blank=True
    )
    original_start_time = models.TimeField(null=True, blank=True)
    original_end_time   = models.TimeField(null=True, blank=True)
    is_rescheduled      = models.BooleanField(default=False)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "schedule_slots"
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        day = self.get_day_of_week_display()
        status = "booked" if self.booked_by_id else "available"
        return (
            f"{self.delivery_format} – {day} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M} ({status})"
        )

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = ScheduleSlot.objects.get(pk=self.pk)
                time_changed = old.start_time != self.start_time or old.end_time != self.end_time
                day_changed  = old.day_of_week != self.day_of_week
            except ScheduleSlot.DoesNotExist:
                time_changed = day_changed = False
        else:
            time_changed = day_changed = False

        super().save(*args, **kwargs)

        if time_changed or day_changed:
            from apps.courses.models.Session import Session
            today = date.today()
            future = Session.objects.filter(
                slot=self,
                date__gte=today,
                status=Session.Status.SCHEDULED,
                rescheduled_from_date__isnull=True,
            )
            if day_changed:
                future.delete()
            else:
                future.update(start_time=self.start_time, end_time=self.end_time)

    @property
    def is_available(self) -> bool:
        return self.booked_by_id is None
