from django.db import models


class LessonCompletion(models.Model):
    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="lesson_completions",
    )
    lesson = models.ForeignKey(
        "curriculum.Lesson",
        on_delete=models.CASCADE,
        related_name="completions",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lesson_completions"
        ordering = ["-completed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "lesson"],
                name="unique_lesson_completion_per_enrollment",
            ),
        ]

    def __str__(self):
        return f"{self.enrollment_id} done lesson {self.lesson_id}"
