from django.contrib import admin

from apps.blog.models import Article, ArticleModerationSnapshot, BlogCategory


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ["name_en", "slug", "order", "is_deleted"]
    search_fields = ["name_en", "name_uk", "name_fr", "name_es", "name_de", "slug"]
    ordering = ["order", "name_en"]
    prepopulated_fields = {"slug": ("name_en",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "category", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["title", "author__email"]


@admin.register(ArticleModerationSnapshot)
class ArticleModerationSnapshotAdmin(admin.ModelAdmin):
    list_display = ["title", "decision", "moderator_profile", "created_at"]
    list_filter = ["decision"]
    search_fields = ["title", "article__title"]
