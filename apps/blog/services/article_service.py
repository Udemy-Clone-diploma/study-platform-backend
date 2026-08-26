from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.exceptions import (
    ArticleAlreadyAssignedError,
    ArticleNotAssignedToModeratorError,
    BlogError,
)
from apps.blog.models import Article, ArticleModerationSnapshot
from apps.common.files import duplicate_file_field
from apps.users.models import User

_STAFF_ROLES = (User.RoleChoices.MODERATOR, User.RoleChoices.ADMINISTRATOR)


class ArticleService:
    @classmethod
    def _build_unique_slug(cls, base_value: str, article: Article | None = None) -> str:
        base_slug = slugify(base_value) or "article"
        candidate = base_slug
        suffix = 2

        queryset = Article.all_objects.all()
        if article is not None:
            queryset = queryset.exclude(pk=article.pk)

        while queryset.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate

    @classmethod
    def _apply_slug(cls, validated_data: dict, article: Article | None = None) -> dict:
        title = validated_data.get("title", article.title if article else "")

        if article is None:
            validated_data["slug"] = cls._build_unique_slug(title)
            return validated_data

        title_changed = "title" in validated_data and validated_data["title"] != article.title
        can_regenerate = (
            article.status in (Article.StatusChoices.DRAFT, Article.StatusChoices.REJECTED)
            and title_changed
        )
        if can_regenerate:
            validated_data["slug"] = cls._build_unique_slug(title, article)

        return validated_data

    @classmethod
    @transaction.atomic
    def create_article(cls, author: User, validated_data: dict) -> Article:
        """Every article starts as a draft, regardless of who authors it.

        Teachers move it forward with submit_for_review(); moderators/admins use
        publish_own_article() to skip the review step entirely.
        """
        data = cls._apply_slug(dict(validated_data))
        return Article.objects.create(author=author, status=Article.StatusChoices.DRAFT, **data)

    @classmethod
    @transaction.atomic
    def update_article(cls, article: Article, user: User, validated_data: dict) -> Article:
        is_staff = user.role in _STAFF_ROLES
        if not is_staff and article.status not in (
            Article.StatusChoices.DRAFT,
            Article.StatusChoices.REJECTED,
        ):
            raise BlogError("Withdraw this article to draft before editing it.")
        data = cls._apply_slug(dict(validated_data), article)
        for field, value in data.items():
            setattr(article, field, value)
        article.save()
        return article

    @classmethod
    def submit_for_review(cls, article: Article, user: User) -> Article:
        """Teacher sends a draft/rejected article into the shared moderation queue.

        The moderator_comment is intentionally kept (not cleared) so whoever
        reviews it next can see the previous verdict; it's only cleared on approve.
        """
        if article.author_id != user.id:
            raise BlogError("Only the article's author can submit it for review.")
        if user.role != User.RoleChoices.TEACHER:
            raise BlogError("Only teacher-authored articles go through moderation.")
        if article.status not in (Article.StatusChoices.DRAFT, Article.StatusChoices.REJECTED):
            raise BlogError("Only draft or rejected articles can be submitted for review.")
        article.status = Article.StatusChoices.REVIEW
        article.moderator_profile = None
        article.save(update_fields=["status", "moderator_profile", "updated_at"])
        return article

    @classmethod
    def publish_own_article(cls, article: Article, user: User) -> Article:
        """Moderators/admins skip review: publish their own draft directly."""
        if article.author_id != user.id:
            raise BlogError("Only the article's author can publish it directly.")
        if user.role not in _STAFF_ROLES:
            raise BlogError("Only moderators or administrators can publish without review.")
        if article.status != Article.StatusChoices.DRAFT:
            raise BlogError("Only draft articles can be published directly.")
        article.status = Article.StatusChoices.PUBLISHED
        article.published_at = timezone.now()
        article.moderator_comment = ""
        article.save(update_fields=["status", "published_at", "moderator_comment", "updated_at"])
        return article

    @classmethod
    def withdraw_to_draft(cls, article: Article, user: User) -> Article:
        """Author pulls a submitted or live article back to draft to edit it."""
        if article.author_id != user.id:
            raise BlogError("Only the article's author can withdraw it.")
        if article.status not in (Article.StatusChoices.REVIEW, Article.StatusChoices.PUBLISHED):
            raise BlogError("Only articles under review or published can be withdrawn to draft.")
        article.status = Article.StatusChoices.DRAFT
        article.moderator_profile = None
        article.save(update_fields=["status", "moderator_profile", "updated_at"])
        return article

    @classmethod
    def archive_article(cls, article: Article, user: User) -> Article:
        is_staff = user.role in _STAFF_ROLES
        if not is_staff:
            if article.author_id != user.id:
                raise BlogError("Only the article's author (or staff) can archive it.")
            if article.status != Article.StatusChoices.PUBLISHED:
                raise BlogError("Only published articles can be archived.")
        article.status = Article.StatusChoices.ARCHIVED
        article.save(update_fields=["status", "updated_at"])
        return article

    @classmethod
    def restore_from_archive(cls, article: Article, user: User) -> Article:
        is_staff = user.role in _STAFF_ROLES
        if not is_staff and article.author_id != user.id:
            raise BlogError("Only the article's author (or staff) can restore it.")
        if article.status != Article.StatusChoices.ARCHIVED:
            raise BlogError("Only archived articles can be restored.")
        article.status = Article.StatusChoices.DRAFT
        article.save(update_fields=["status", "updated_at"])
        return article

    @classmethod
    def delete_article(cls, article: Article, user: User) -> None:
        # Staff can archive any article (see archive_article) but only ever delete their own:
        # deleting someone else's work outright isn't a moderation action, just archiving is.
        if article.author_id != user.id:
            raise BlogError(
                "Only the article's author can delete it. Staff can archive it instead."
            )
        if article.status in (Article.StatusChoices.REVIEW, Article.StatusChoices.PUBLISHED):
            raise BlogError("Withdraw or archive this article before deleting it.")
        article.is_deleted = True
        article.save(update_fields=["is_deleted", "updated_at"])

    @classmethod
    def assign_moderator_self(cls, article: Article, moderator_profile) -> Article:
        if moderator_profile is None:
            raise BlogError("Authenticated user does not have a moderator profile.")
        if article.status != Article.StatusChoices.REVIEW:
            raise BlogError("Only articles under review can be assigned.")
        if article.moderator_profile_id is not None:
            raise ArticleAlreadyAssignedError
        article.moderator_profile = moderator_profile
        article.save(update_fields=["moderator_profile", "updated_at"])
        return article

    @classmethod
    def _create_snapshot(
        cls, article: Article, moderator_profile, decision: str, comment: str = ""
    ) -> None:
        """Freezes the article's current display fields into a permanent moderation
        record, see ArticleModerationSnapshot for why this exists instead of relying
        on the live Article row (which keeps mutating after the decision)."""
        snapshot = ArticleModerationSnapshot(
            article=article,
            moderator_profile=moderator_profile,
            decision=decision,
            comment=comment,
            title=article.title,
            subtitle=article.subtitle,
            cover_crops=article.cover_crops,
            author_name=article.author.get_full_name(),
        )
        duplicate_file_field(article.cover_image, snapshot.cover_image)
        snapshot.save()

    @classmethod
    @transaction.atomic
    def approve_article(cls, article: Article, moderator_profile) -> Article:
        if article.status != Article.StatusChoices.REVIEW:
            raise BlogError("Only articles under review can be approved.")
        if article.moderator_profile_id != getattr(moderator_profile, "id", None):
            raise ArticleNotAssignedToModeratorError
        article.status = Article.StatusChoices.PUBLISHED
        article.published_at = timezone.now()
        article.moderator_comment = ""
        article.save(update_fields=["status", "published_at", "moderator_comment", "updated_at"])
        cls._create_snapshot(
            article, moderator_profile, ArticleModerationSnapshot.Decision.PUBLISHED
        )
        return article

    @classmethod
    @transaction.atomic
    def reject_article(cls, article: Article, moderator_profile, comment: str) -> Article:
        if article.status != Article.StatusChoices.REVIEW:
            raise BlogError("Only articles under review can be rejected.")
        if article.moderator_profile_id != getattr(moderator_profile, "id", None):
            raise ArticleNotAssignedToModeratorError
        article.status = Article.StatusChoices.REJECTED
        article.moderator_comment = comment
        article.save(update_fields=["status", "moderator_comment", "updated_at"])
        cls._create_snapshot(
            article, moderator_profile, ArticleModerationSnapshot.Decision.REJECTED, comment
        )
        return article
