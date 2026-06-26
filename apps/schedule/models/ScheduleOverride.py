from django.db import models

from .CohortSchedule import CohortSchedule
from .ScheduleSlot import ScheduleSlot


class ScheduleOverride(models.Model):
    """
    One-off override for a single occurrence of a recurring ScheduleSlot or CohortSchedule.

    Exactly one of `slot` or `schedule` must be set.
    `original_date` identifies which weekly occurrence is affected.
    When status='rescheduled', the replacement event details are in new_date / new_*_time.
    """

    class Status(models.TextChoices):
        CANCELLED   = "cancelled",   "Cancelled"
        RESCHEDULED = "rescheduled", "Rescheduled"

    slot = models.ForeignKey(
        ScheduleSlot,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="overrides",
    )
    schedule = models.ForeignKey(
        CohortSchedule,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="overrides",
    )

    original_date  = models.DateField()
    status         = models.CharField(max_length=20, choices=Status.choices)

    new_date       = models.DateField(null=True, blank=True)
    new_start_time = models.TimeField(null=True, blank=True)
    new_end_time   = models.TimeField(null=True, blank=True)
    meeting_link   = models.URLField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "schedule_overrides"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(slot__isnull=False, schedule__isnull=True)
                    | models.Q(slot__isnull=True, schedule__isnull=False)
                ),
                name="schedule_override_exactly_one_source",
            ),
        ]

    def __str__(self):
        src = f"slot#{self.slot_id}" if self.slot_id else f"schedule#{self.schedule_id}"
        return f"{src} on {self.original_date}: {self.status}"
