from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .User import User


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
    )

    def __str__(self):
        return f"TeacherProfile: {self.user.email}"

    def clean(self):
        if self.user.role != "teacher":
            raise ValidationError(
                "This profile can only be created for a user with the 'teacher' role."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
