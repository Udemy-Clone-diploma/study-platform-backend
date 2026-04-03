from django.core.exceptions import ValidationError
from django.db import models

from .User import User


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    specialization = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"TeacherProfile: {self.user.email}"

    def clean(self):
        if self.user.role != "teacher":
            raise ValidationError(
                "Цей профіль можна створювати лише для користувача з роллю 'teacher'"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
