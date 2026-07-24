from django.conf import settings
from django.db import models
from django.db.models import Q


class UserReport(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_REVIEW = "in_review", "In review"
        ESCALATED = "escalated", "Escalated"
        RESOLVED = "resolved", "Resolved"

    class ResolutionChoices(models.TextChoices):
        WARNING = "warning", "Warning"
        BLOCKED = "blocked", "Blocked"
        UNBLOCKED = "unblocked", "Unblocked"
        DISMISSED = "dismissed", "Dismissed"

    class ReasonChoices(models.TextChoices):
        SPAM = "spam", "Spam or advertising"
        HARASSMENT = "harassment", "Harassment or bullying"
        HATE = "hate", "Hate speech"
        VIOLENCE = "violence", "Violence or threats"
        SEXUAL = "sexual", "Sexual content"
        FRAUD = "fraud", "Fraud or scam"
        IMPERSONATION = "impersonation", "Impersonation"
        INAPPROPRIATE_PROFILE = "inappropriate_profile", "Inappropriate profile"
        OTHER = "other", "Other"

    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_reports_received",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_reports_submitted",
    )
    reason = models.CharField(max_length=24, choices=ReasonChoices.choices)
    details = models.CharField(max_length=500, blank=True, default="")
    profile_snapshot = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    resolution = models.CharField(
        max_length=16,
        choices=ResolutionChoices.choices,
        blank=True,
        default="",
    )
    assigned_moderator = models.ForeignKey(
        "users.ModeratorProfile",
        on_delete=models.SET_NULL,
        related_name="assigned_user_reports",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="user_reports_escalated",
        null=True,
        blank=True,
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_note = models.CharField(max_length=500, blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="user_reports_resolved",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_reports"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reported_user", "reporter"],
                condition=Q(
                    status__in=[
                        "pending",
                        "in_review",
                        "escalated",
                    ]
                ),
                name="unique_active_user_reporter_target",
            ),
        ]
        indexes = [
            models.Index(
                fields=["reported_user", "-created_at"],
                name="user_report_target_created_idx",
            ),
            models.Index(
                fields=["status", "assigned_moderator", "created_at"],
                name="user_report_queue_idx",
            ),
        ]

    def __str__(self):
        return f"{self.reporter_id} -> user #{self.reported_user_id}"
