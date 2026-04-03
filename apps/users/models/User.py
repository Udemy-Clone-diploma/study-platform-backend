from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class ActiveUserManager(UserManager):
    """Returns only non-deleted users."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("uk", "Ukrainian"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")
    is_blocked = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveUserManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.email
