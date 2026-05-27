from django.db import models

from .Course import Course


class Cohort(models.Model):
    class DeliveryModeChoices(models.TextChoices):
        GROUP = "group", "Group"
        INDIVIDUAL = "individual", "Individual"
        BOTH = "both", "Both"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="cohorts",
    )
    duration_months = models.PositiveSmallIntegerField()
    hours_per_week_min = models.PositiveSmallIntegerField()
    hours_per_week_max = models.PositiveSmallIntegerField()
    group_size = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_mode = models.CharField(
        max_length=20, choices=DeliveryModeChoices.choices,
    )
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "cohorts"
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.course.title} cohort ({self.start_date or 'TBD'})"
