from django.db import models


class TeacherUnavailability(models.Model):
    """
    A time block where a teacher is unavailable: personal plans, vacation, etc.

    Two recurrence types:
    - weekly: repeats every week on the given day_of_week (date is ignored).
    - one_time: a specific calendar date (day_of_week is derived from date but stored
                for quick conflict queries without joining).

    These blocks are respected by the teacher conflict validator alongside
    ScheduleSlots and CohortSchedules, no class of any type can overlap them.
    """

    class RecurrenceType(models.TextChoices):
        WEEKLY = "weekly", "Every week"
        ONE_TIME = "one_time", "One-time block"
        DATE_RANGE = "date_range", "Date range"

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    teacher_profile = models.ForeignKey(
        "users.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="unavailabilities",
    )
    recurrence_type = models.CharField(
        max_length=10, choices=RecurrenceType.choices, default=RecurrenceType.WEEKLY
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    date = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "teacher_unavailabilities"
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        day = self.get_day_of_week_display()
        recurrence = self.get_recurrence_type_display()
        return (
            f"{self.teacher_profile} – {recurrence} {day} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )
