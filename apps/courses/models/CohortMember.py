from django.db import models

from .Cohort import Cohort


class CohortMember(models.Model):
    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="members",
    )
    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="cohort_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cohort_members"
        unique_together = [("cohort", "enrollment")]

    def __str__(self):
        return f"{self.cohort} — {self.enrollment.student_profile.user.email}"
