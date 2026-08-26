from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from apps.common.files import UUIDUploadTo, file_content_hash
from apps.common.managers import ActiveManager
from apps.users.models import ModeratorProfile

from .BlogCategory import BlogCategory

ARTICLE_IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "jfif", "webp", "svg"]

# The distinct cover-image aspect ratios actually rendered across the frontend --
# every place that shows Article.cover_image maps to exactly one of these:
#   card:   46/52 -- ArticleCard (public blog grid), StudentStoryCard (homepage)
#   row:    4/3   -- ArticleRow (teacher/moderator/admin "my articles" list)
#   banner: 16/9  -- ArticleDetailPanel (dashboard preview), ArticleDetailView (article page)
# Keep this tuple and the frontend's COVER_CROP_SLOTS (entities/blog) in sync.
COVER_CROP_SLOTS = ("card", "row", "banner")


def default_cover_crops() -> dict:
    return {slot: {"x": 0, "y": 0, "width": 100, "height": 100} for slot in COVER_CROP_SLOTS}


class Article(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Under Review"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=255)

    slug = models.SlugField(unique=True, max_length=280)

    subtitle = models.CharField(max_length=500, blank=True, default="")

    cover_image = models.FileField(
        upload_to=UUIDUploadTo("blog"),
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=ARTICLE_IMAGE_EXTENSIONS)],
    )
    # Cached MD5 of `cover_image`'s bytes. See Course.image_hash for why.
    cover_image_hash = models.CharField(max_length=32, blank=True, default="")

    # Per-format crop box: {"card": {"x", "y", "width", "height"}, "row": {...}, "banner": {...}}
    # -- see COVER_CROP_SLOTS above. x/y/width/height are percentages (0-100) of the
    # image, x/y being the box's top-left corner -- the same shape react-easy-crop's
    # onCropComplete/initialCroppedAreaPercentages use. Each rendered shape gets its
    # own crop since one shared focal point reads fine on some aspect ratios but
    # clips the subject on others.
    cover_crops = models.JSONField(default=default_cover_crops)

    body_html = models.TextField(blank=True, default="")

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )

    # Set once a teacher submits for review and a moderator claims it from the
    # unassigned queue (see ArticleService.assign_moderator_self). Reset to
    # null whenever the article leaves REVIEW (withdrawn or resubmitted).
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_articles",
    )

    # Persists across draft -> review -> rejected cycles so a moderator can see
    # their own prior verdict on re-review; cleared only once approved.
    moderator_comment = models.TextField(blank=True, default="")

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "blog_articles"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        recompute = update_fields is None or (
            "cover_image" in update_fields and "cover_image_hash" not in update_fields
        )
        if recompute:
            self.cover_image_hash = file_content_hash(self.cover_image) or ""
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "cover_image_hash"]
        super().save(*args, **kwargs)
