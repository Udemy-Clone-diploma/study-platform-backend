from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.files import UUIDUploadTo, file_content_hash
from apps.common.managers import ActiveManager
from apps.users.models import ModeratorProfile, TeacherProfile

COURSE_IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "webp", "svg"]

from .Category import Category
from .Tag import Tag


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
        SCHEDULED = "scheduled", "Scheduled"
        INDIVIDUAL = "individual", "Individual"
        GROUP = "group", "Group"

    class CourseTypeChoices(models.TextChoices):
        PROFESSION = "profession", "Profession"
        QUALIFICATION = "qualification", "Qualification"
        KNOWLEDGE = "knowledge", "Knowledge"

    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        NEEDS_REVISION = "needs_revision", "Needs Revision (returned by moderator)"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        HIDDEN = "hidden", "Hidden (active but not listed)"
        ARCHIVED = "archived", "Archived"
        PENDING_EDIT = "pending_edit", "Pending Edit (hidden shadow draft of a published course)"

    # FileField (not ImageField) because Pillow (which ImageField uses to validate) cannot
    # open SVGs, and the default course icons are SVGs. Extension check stands in for that.
    image = models.FileField(
        upload_to=UUIDUploadTo("courses"),
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=COURSE_IMAGE_EXTENSIONS)],
    )
    # Cached MD5 of `image`'s bytes. See LessonItem.video_hash for why.
    image_hash = models.CharField(max_length=32, blank=True, default="")

    title = models.CharField(max_length=255, db_index=True)

    subtitle = models.CharField(max_length=255, blank=True, null=True)

    short_description = models.CharField(max_length=500)

    full_description = models.TextField()

    slug = models.SlugField(unique=True)

    teacher_profile = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="courses",
    )

    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_courses",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )

    level = models.CharField(max_length=20, choices=LevelChoices.choices)

    language = models.CharField(
        max_length=20,
        choices=LanguageChoices.choices,
        default=LanguageChoices.UKRAINIAN,
    )

    mode = models.CharField(max_length=20, choices=ModeChoices.choices)

    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryTypeChoices.choices,
    )

    course_type = models.CharField(
        max_length=30,
        choices=CourseTypeChoices.choices,
    )

    duration_hours = models.PositiveIntegerField(null=True, blank=True, default=0)

    lessons_count = models.PositiveIntegerField(default=0)

    with_certificate = models.BooleanField(default=False)


    certificate_description = models.TextField(blank=True, default="")

    is_on_sale = models.BooleanField(default=False)

    discount_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )

    passing_score = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )

    rating_count = models.PositiveIntegerField(default=0)

    students_count = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )

    moderator_comment = models.TextField(blank=True, default="")

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    updated_at = models.DateTimeField(auto_now=True)

    published_at = models.DateTimeField(null=True, blank=True)

    tags = models.ManyToManyField(Tag, blank=True, related_name="courses")

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "courses"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.is_on_sale and not self.discount_percent:
            raise ValidationError({"discount_percent": "Required when is_on_sale is enabled."})

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        recompute = update_fields is None or ("image" in update_fields and "image_hash" not in update_fields)
        if recompute:
            self.image_hash = file_content_hash(self.image) or ""
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "image_hash"]
        super().save(*args, **kwargs)
