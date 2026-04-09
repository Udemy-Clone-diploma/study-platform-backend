from django.core.exceptions import ValidationError
from django.db import models

from .User import User


class ModeratorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level = models.CharField(max_length=50)

    def __str__(self):
        return f"ModeratorProfile: {self.user.email}"

    def clean(self):
        if self.user.role != "moderator":
            raise ValidationError(
                "This profile can only be created for a user with the 'moderator' role."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
