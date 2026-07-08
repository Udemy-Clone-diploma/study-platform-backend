from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.managers import ActiveManager
from apps.courses.models import Course
from apps.users.models import ModeratorProfile


class Review(models.Model):
    class ModerationStatusChoices(models.TextChoices):
        PENDING = "pending", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    # Set once this review has enough reports to enter the moderation queue and
    # a moderator has claimed it (see ReviewService.assign_moderator_self).
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
    )
    moderation_status = models.CharField(
        max_length=20, choices=ModerationStatusChoices.choices, blank=True, default="",
    )
    # Rejecting a reported review hides it (rather than hard-deleting) so the
    # moderation record/history stays intact.
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "student"], name="unique_review_per_student_course",
            ),
        ]

    def __str__(self):
        return f"{self.student.email} -> {self.course.title} ({self.rating})"
