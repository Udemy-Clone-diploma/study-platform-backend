from django.db import models

from .Course import Course


class CourseDeliveryFormat(models.Model):
    class FormatType(models.TextChoices):
        SELF_PACED  = "self_paced",  "Self-paced"
        SCHEDULED   = "scheduled",   "Scheduled"
        INDIVIDUAL  = "individual",  "Individual (1-on-1 with teacher)"
        GROUP       = "group",       "Group (with teacher)"

    class StartType(models.TextChoices):
        DATE   = "date",   "Specific start date"
        MANUAL = "manual", "Manual activation"

    class UnlockMode(models.TextChoices):
        IMMEDIATE  = "immediate",  "All content unlocked immediately"
        DATE_BASED = "date_based", "Unlock by date from course start"
        SEQUENTIAL = "sequential", "Unlock after completing previous lesson"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="delivery_formats",
    )
    group_chat = models.OneToOneField(
        "chat.ChatRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_format_group",
    )
    format_type = models.CharField(max_length=20, choices=FormatType.choices)

    # --- self_paced fields ---
    start_type = models.CharField(
        max_length=10, choices=StartType.choices,
        null=True, blank=True,
    )
    course_start_date = models.DateField(null=True, blank=True)
    # 0 = lifetime access; null = not configured yet
    access_duration_days = models.PositiveIntegerField(null=True, blank=True)

    # --- scheduled / group fields ---
    start_date = models.DateField(null=True, blank=True)
    unlock_mode = models.CharField(
        max_length=20, choices=UnlockMode.choices,
        null=True, blank=True,
    )

    # --- individual fields ---
    # max concurrent students the teacher accepts under this format
    max_students = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "course_delivery_formats"
        ordering = ["format_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "format_type"],
                name="unique_delivery_format_per_course",
            ),
        ]

    def __str__(self):
        return f"{self.course.title} – {self.get_format_type_display()}"
