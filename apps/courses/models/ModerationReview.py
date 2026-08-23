from django.db import models

from apps.users.models import ModeratorProfile


class ModerationReview(models.Model):
    """Per-course moderator feedback snapshot for the initial review cycle, stored until the course is approved or rejected"""

    course = models.OneToOneField(
        "Course",
        on_delete=models.CASCADE,
        related_name="moderation_review",
    )
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_reviews",
    )
    # Step 1: Basics
    basics_field_statuses = models.JSONField(default=dict, blank=True)
    basics_action = models.CharField(max_length=20, blank=True, default="")
    basics_comment = models.TextField(blank=True, default="")

    # Step 2: Content
    content_item_statuses = models.JSONField(default=dict, blank=True)
    content_action = models.CharField(max_length=20, blank=True, default="")
    content_comment = models.TextField(blank=True, default="")

    # Step 3: Review & Publish
    final_action = models.CharField(max_length=20, blank=True, default="")
    final_comment = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "course_moderation_reviews"

    def __str__(self):
        return f"ModerationReview for {self.course_id}"
