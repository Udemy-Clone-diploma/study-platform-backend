from datetime import date

from django.db import models


class CohortSchedule(models.Model):
    """
    A fixed recurring weekly class session for a group cohort.

    The schedule is stable — it does not change once set.
    Students can view it before purchasing to evaluate fit.
    Teacher conflict validator ensures no two sessions (of any kind) overlap.
    """

    class DayOfWeek(models.IntegerChoices):
        MONDAY    = 0, "Monday"
        TUESDAY   = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY  = 3, "Thursday"
        FRIDAY    = 4, "Friday"
        SATURDAY  = 5, "Saturday"
        SUNDAY    = 6, "Sunday"

    cohort = models.ForeignKey(
        "courses.Cohort",
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    day_of_week  = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    start_time   = models.TimeField()
    end_time     = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cohort_schedules"
        ordering = ["day_of_week", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["cohort", "day_of_week", "start_time"],
                name="unique_cohort_schedule_slot",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = CohortSchedule.objects.get(pk=self.pk)
                time_changed = old.start_time != self.start_time or old.end_time != self.end_time
                day_changed  = old.day_of_week != self.day_of_week
            except CohortSchedule.DoesNotExist:
                time_changed = day_changed = False
        else:
            time_changed = day_changed = False

        super().save(*args, **kwargs)

        if time_changed or day_changed:
            from apps.schedule.models.Session import Session
            today = date.today()
            future = Session.objects.filter(
                schedule=self,
                date__gte=today,
                status=Session.Status.SCHEDULED,
                rescheduled_from_date__isnull=True,
            )
            if day_changed:
                future.delete()
            else:
                future.update(start_time=self.start_time, end_time=self.end_time)

    def __str__(self):
        day = self.get_day_of_week_display()
        return (
            f"{self.cohort} – {day} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )
