from django.db import models


class Session(models.Model):
    """
    One concrete occurrence of a recurring ScheduleSlot/CohortSchedule,
    or a manually-created extra lesson by a teacher.
    Exactly one source must be non-null: slot, schedule, or course.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"
        RESCHEDULED = "rescheduled", "Rescheduled"

    slot = models.ForeignKey(
        "ScheduleSlot",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions",
    )
    schedule = models.ForeignKey(
        "CohortSchedule",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    cohort = models.ForeignKey(
        "courses.Cohort",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    meeting_link = models.URLField(null=True, blank=True)
    lesson = models.ForeignKey(
        "curriculum.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    rescheduled_to_date = models.DateField(null=True, blank=True)
    rescheduled_from_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sessions"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(slot__isnull=False, schedule__isnull=True, course__isnull=True)
                    | models.Q(slot__isnull=True, schedule__isnull=False, course__isnull=True)
                    | models.Q(slot__isnull=True, schedule__isnull=True, course__isnull=False)
                ),
                name="session_source_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["schedule", "date"]),
            models.Index(fields=["slot", "date"]),
            models.Index(fields=["course", "date"]),
        ]

    def __str__(self):
        source = self.slot or self.schedule or self.course
        return f"Session {self.date} – {source}"
