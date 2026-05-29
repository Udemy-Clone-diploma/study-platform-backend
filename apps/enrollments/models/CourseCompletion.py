from django.db import models


class CourseCompletion(models.Model):
    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="course_completions",
        db_column="id_student_profile",
    )
    # Nullable so the record survives if the course is later hard-deleted.
    # All display data comes from the snapshot fields below, not from this FK.
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completions",
        db_column="id_course",
    )
    # Snapshot fields -- frozen at completion time, independent of future course edits
    title = models.CharField(max_length=255)
    teacher_name = models.CharField(max_length=255)
    level = models.CharField(max_length=20)
    image_url = models.TextField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(auto_now_add=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    certificate_url = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "course_completions"
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.student_profile.user.email} completed {self.title!r}"
