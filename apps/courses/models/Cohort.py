from django.db import models

from .Course import Course


class Cohort(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="cohorts",
    )
    # Nullable FK to CourseDeliveryFormat with format_type=group.
    # Existing cohorts (pre-migration) may have this as NULL.
    delivery_format = models.ForeignKey(
        "courses.CourseDeliveryFormat",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cohorts",
    )
    duration_months = models.PositiveSmallIntegerField()
    hours_per_week_min = models.PositiveSmallIntegerField()
    hours_per_week_max = models.PositiveSmallIntegerField()
    group_size = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    enrollment_deadline = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "cohorts"
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.course.title} cohort ({self.start_date or 'TBD'})"
