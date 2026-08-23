from django.db import models

from apps.common.files import UUIDUploadTo, file_content_hash
from apps.common.managers import ActiveManager

from .Lesson import Lesson
from .Test import Test


class LessonItem(models.Model):
    class ItemType(models.TextChoices):
        TEXT = "text", "Text"
        VIDEO = "video", "Video"
        TEST = "test", "Test"

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(max_length=10, choices=ItemType.choices)
    order = models.PositiveSmallIntegerField()

    # TEXT
    body_html = models.TextField(blank=True, null=True)

    # VIDEO
    video = models.FileField(
        upload_to=UUIDUploadTo("lesson_items/videos"),
        null=True,
        blank=True,
    )
    video_url = models.URLField(blank=True, null=True)
    original_video_name = models.CharField(max_length=255, blank=True, default="")
    # Cached MD5 of `video`'s bytes, computed on save so the moderator-diff view
    # can compare content without re-reading and re-hashing the full file on every request.
    video_hash = models.CharField(max_length=32, blank=True, default="")
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)

    # TEST (at most one per lesson, enforced in service layer)
    test = models.ForeignKey(
        Test,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lesson_items",
    )

    # Set only on a pending-edit draft course's items: points back at the live
    # item this one was cloned from, so approval can merge changes in place.
    source_lesson_item = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_copies",
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "lesson_items"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "order"],
                condition=models.Q(is_deleted=False),
                name="unique_active_lesson_item_order",
            ),
            models.UniqueConstraint(
                fields=["source_lesson_item"],
                condition=models.Q(source_lesson_item__isnull=False),
                name="unique_source_lesson_item",
            ),
        ]

    def __str__(self):
        return f"{self.get_item_type_display()} #{self.order} (lesson {self.lesson_id})"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        # Skip recompute when the caller already supplied video_hash explicitly
        # (cloning/merging copies it straight from the source item, since a
        # byte-identical duplicate always has the same hash).
        recompute = update_fields is None or (
            "video" in update_fields and "video_hash" not in update_fields
        )
        if recompute:
            self.video_hash = file_content_hash(self.video) or ""
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "video_hash"]
        super().save(*args, **kwargs)
