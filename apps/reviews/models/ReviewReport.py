from django.conf import settings
from django.db import models

from .Review import Review


class ReviewReport(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_reports",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_reports"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["review", "reporter"], name="unique_report_per_user_review",
            ),
        ]

    def __str__(self):
        return f"{self.reporter.email} -> review #{self.review_id}"
