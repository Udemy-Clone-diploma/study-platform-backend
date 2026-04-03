from django.core.exceptions import ValidationError
from django.db import models

from .User import User


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)
    learning_goals = models.TextField(blank=True)
    education_level = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"StudentProfile: {self.user.email}"

    def clean(self):
        if self.user.role != "student":
            raise ValidationError(
                "Цей профіль можна створювати лише для користувача з роллю 'student'"
            )
