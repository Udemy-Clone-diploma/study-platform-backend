from django.core.exceptions import ValidationError
from django.db import models

from .User import User


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    learning_goals = models.TextField(blank=True)
    education_level = models.CharField(max_length=100, blank=True)
    courses = models.ManyToManyField("courses.Course", blank=True, related_name="enrolled_students")
    wishlisted_courses = models.ManyToManyField("courses.Course", blank=True, related_name="wishlisted_by")
    def __str__(self):
        return f"StudentProfile: {self.user.email}"

    def clean(self):
        if self.user.role != "student":
            raise ValidationError(
                "This profile can only be created for a user with the 'student' role."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
