from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.blog.models import Article, BlogCategory
from apps.blog.views.ArticleViews import ArticleListCreateView
from apps.courses.tests._factories import make_teacher


class PublicBlogCacheTests(APITestCase):
    def setUp(self):
        self.author, _ = make_teacher(email="blog-cache-author@example.com")
        self.category = BlogCategory.objects.create(
            name="Caching",
            slug="caching",
            description="Cache articles",
        )
        self.article = Article.objects.create(
            title="Public cached article",
            slug="public-cached-article",
            subtitle="Public subtitle",
            body_html="<p>Public body</p>",
            moderator_comment="Internal moderation note",
            author=self.author,
            category=self.category,
            status=Article.StatusChoices.PUBLISHED,
            published_at=timezone.now(),
        )
        cache.clear()

    def test_public_list_reuses_cache_and_uses_safe_serializer(self):
        url = reverse("blog-articles")
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertNotIn("moderator_comment", first.data[0])
        self.assertFalse(first.data[0]["is_assigned_to_me"])

        with patch.object(
            ArticleListCreateView,
            "get_queryset",
            side_effect=AssertionError("public articles should come from cache"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.data[0]["title"], "Public cached article")

    def test_public_detail_hides_moderation_fields(self):
        response = self.client.get(
            reverse("blog-article-detail", args=[self.article.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["body_html"], "<p>Public body</p>")
        self.assertEqual(response.data["moderator_comment"], "")
        self.assertFalse(response.data["is_assigned_to_me"])

    def test_owner_keeps_internal_detail_shape(self):
        self.client.force_authenticate(self.author)
        response = self.client.get(
            reverse("blog-article-detail", args=[self.article.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["moderator_comment"],
            "Internal moderation note",
        )

    def test_article_change_invalidates_public_list(self):
        url = reverse("blog-articles")
        self.client.get(url)

        with self.captureOnCommitCallbacks(execute=True):
            self.article.title = "Updated public article"
            self.article.save(update_fields=["title", "updated_at"])

        response = self.client.get(url)
        self.assertEqual(response.data[0]["title"], "Updated public article")

    def test_category_count_contains_only_published_articles(self):
        Article.objects.create(
            title="Draft",
            slug="draft-not-counted",
            author=self.author,
            category=self.category,
            status=Article.StatusChoices.DRAFT,
        )
        response = self.client.get(reverse("blog-categories"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        category = next(
            item for item in response.data if item["slug"] == self.category.slug
        )
        self.assertEqual(category["articles_count"], 1)

    def test_category_list_reuses_cache(self):
        url = reverse("blog-categories")
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch(
            "apps.blog.views.BlogCategoryViews."
            "BlogCategoryService.annotate_articles_count",
            side_effect=AssertionError("categories should come from cache"),
        ):
            second = self.client.get(url)

        self.assertIn("caching", [item["slug"] for item in second.data])
