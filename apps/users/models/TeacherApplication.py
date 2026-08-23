from django.conf import settings
from django.db import models

from apps.courses.models import Category

from .ModeratorProfile import ModeratorProfile


class TeacherApplication(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        CANCELLED = "cancelled", "Cancelled"

    # Identity / contact: shown to the moderator as a separate "contact data" block.
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    # Profile info: mirrors TeacherProfile so approval can copy it 1:1.
    bio = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)

    # Additional info: moderator-review-only, never copied onto TeacherProfile/User.
    directions = models.ManyToManyField(Category, blank=True, related_name="teacher_applications")
    motivation = models.TextField(blank=True)
    instagram = models.URLField(blank=True, default="")
    linkedin = models.URLField(blank=True, default="")
    behance = models.URLField(blank=True, default="")

    # Workflow.
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_application_decisions",
    )
    moderator_comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_application",
    )

    class Meta:
        db_table = "teacher_applications"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"TeacherApplication: {self.email} ({self.status})"
