from django.contrib import admin

from apps.blog.models import Article, BlogCategory


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "order", "is_deleted"]
    ordering = ["order", "name"]


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "category", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["title", "author__email"]
