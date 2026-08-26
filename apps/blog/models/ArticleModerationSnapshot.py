from django.db import models

from apps.common.files import UUIDUploadTo
from apps.users.models import ModeratorProfile

from .Article import Article, default_cover_crops


class ArticleModerationSnapshot(models.Model):
    """Permanent record of a moderator's reject/publish decision, independent of the
    live Article row -- which keeps mutating (edited, resubmitted, archived, withdrawn)
    after the decision. Created by ArticleService.reject_article / approve_article;
    never updated afterwards.
    """

    class Decision(models.TextChoices):
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="moderation_snapshots",
    )
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="article_moderation_snapshots",
    )
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comment = models.TextField(blank=True, default="")

    # Copied off the Article at the moment of the decision (see ArticleService),
    # using duplicate_file_field for cover_image so it survives even if the live
    # article's cover_image is later replaced or removed.
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=500, blank=True, default="")
    cover_image = models.FileField(upload_to=UUIDUploadTo("blog-snapshots"), null=True, blank=True)
    # Copied from Article.cover_crops at the moment of the decision, same reason as
    # cover_image above.
    cover_crops = models.JSONField(default=default_cover_crops)
    author_name = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "blog_article_moderation_snapshots"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.decision} snapshot of Article #{self.article_id}"
