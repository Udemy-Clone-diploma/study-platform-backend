from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.users.models import ModeratorProfile, TeacherProfile


class ActiveCourseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Course(models.Model):
    class LevelChoices(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class LanguageChoices(models.TextChoices):
        ENGLISH = "english", "English"
        UKRAINIAN = "ukrainian", "Ukrainian"
        SPANISH = "spanish", "Spanish"

    class ModeChoices(models.TextChoices):
        SELF_LEARNING = "self_learning", "Self Learning"
        WITH_TEACHER = "with_teacher", "With Teacher"

    class DeliveryTypeChoices(models.TextChoices):
        SELF_PACED = "self_paced", "Self-paced"
        SCHEDULED = "scheduled", "Scheduled" # додатково
        INDIVIDUAL = "individual", "Individual"
        GROUP = "group", "Group"

    class CourseTypeChoices(models.TextChoices):
        PROFESSION = "profession", "Profession"
        QUALIFICATION = "qualification", "Qualification"
        KNOWLEDGE = "knowledge", "Knowledge"

    class PricingTypeChoices(models.TextChoices):
        FREE = "free", "Free"
        FULL_PAYMENT = "full_payment", "Full Payment"
        INSTALLMENT = "installment", "Installment"

    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=255)

    short_description = models.CharField(
        max_length=500
    )

    full_description = models.TextField()

    slug = models.SlugField(
        unique=True
    )

    teacher_profile = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="courses"
    )

    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_courses"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses"
    )

    level = models.CharField(
        max_length=20,
        choices=LevelChoices.choices
    )

    language = models.CharField(
        max_length=20,
        choices=LanguageChoices.choices,
        default=LanguageChoices.ENGLISH
    )

    mode = models.CharField(
        max_length=20,
        choices=ModeChoices.choices
    )

    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryTypeChoices.choices
    )

    course_type = models.CharField(
        max_length=30,
        choices=CourseTypeChoices.choices
    )

    pricing_type = models.CharField(
        max_length=20,
        choices=PricingTypeChoices.choices,
        default=PricingTypeChoices.FREE
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00 #type: ignore
    )

    installment_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    installment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    duration_hours = models.PositiveIntegerField()

    lessons_count = models.PositiveIntegerField(
        default=0
    )

    with_certificate = models.BooleanField(
        default=False
    )

    is_on_sale = models.BooleanField(
        default=False
    )

    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00, #type: ignore
        validators=[
            MinValueValidator(0),
            MaxValueValidator(5),
        ]
    )

    students_count = models.PositiveIntegerField(
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )

    is_deleted = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True
    )

    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="courses"
    )

    objects = ActiveCourseManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "courses"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
