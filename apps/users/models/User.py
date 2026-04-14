from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "administrator")
        return self.create_user(email, password, **extra_fields)


class ActiveUserManager(UserManager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class User(AbstractUser):
    username = None

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

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
    is_email_verified = models.BooleanField(default=False)

    objects = ActiveUserManager()
    all_objects = UserManager()

    def __str__(self):
        return self.email
