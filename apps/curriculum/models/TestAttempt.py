from django.db import models

from .Test import Test


class TestAttempt(models.Model):
    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="test_attempts",
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField()
    passed = models.BooleanField()
    # Snapshot of the student's submitted answers, keyed by question id.
    answers = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "test_attempts"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student_profile", "test", "attempt_number"],
                name="unique_attempt_number_per_student_test",
            ),
        ]

    def __str__(self):
        return f"attempt {self.attempt_number} on test {self.test_id} by {self.student_profile_id}"
