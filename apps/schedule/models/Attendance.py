from django.db import models


class Attendance(models.Model):
    session = models.ForeignKey(
        "Session",
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    is_present = models.BooleanField(default=False)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance"
        unique_together = [("session", "enrollment")]

    def __str__(self):
        status = "present" if self.is_present else "absent"
        return f"{self.enrollment.student_profile.user.email} – {self.session.date} ({status})"
