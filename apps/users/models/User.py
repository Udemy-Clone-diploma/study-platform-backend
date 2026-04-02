from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("teacher", "Teacher"),
        ("moderator", "Moderator"),
        ("administrator", "Administrator"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    language = models.CharField(max_length=10, default="en")
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return self.email
