from django.urls import path

from apps.blog.views import (
    ArticleApproveView,
    ArticleArchiveView,
    ArticleAssignModeratorView,
    ArticleDetailView,
    ArticleListCreateView,
    ArticleModerationSnapshotListView,
    ArticlePublishView,
    ArticleRejectView,
    ArticleRestoreView,
    ArticleSubmitReviewView,
    ArticleWithdrawView,
    BlogCategoryDetailView,
    BlogCategoryListCreateView,
)

urlpatterns = [
    path("blog/categories/", BlogCategoryListCreateView.as_view(), name="blog-categories"),
    path(
        "blog/categories/<slug:slug>/",
        BlogCategoryDetailView.as_view(),
        name="blog-category-detail",
    ),
    path(
        "blog/moderation-snapshots/",
        ArticleModerationSnapshotListView.as_view(),
        name="blog-moderation-snapshots",
    ),
    path("blog/articles/", ArticleListCreateView.as_view(), name="blog-articles"),
    path("blog/articles/<slug:slug>/", ArticleDetailView.as_view(), name="blog-article-detail"),
    path(
        "blog/articles/<slug:slug>/submit/",
        ArticleSubmitReviewView.as_view(),
        name="blog-article-submit",
    ),
    path(
        "blog/articles/<slug:slug>/publish/",
        ArticlePublishView.as_view(),
        name="blog-article-publish",
    ),
    path(
        "blog/articles/<slug:slug>/withdraw/",
        ArticleWithdrawView.as_view(),
        name="blog-article-withdraw",
    ),
    path(
        "blog/articles/<slug:slug>/archive/",
        ArticleArchiveView.as_view(),
        name="blog-article-archive",
    ),
    path(
        "blog/articles/<slug:slug>/restore/",
        ArticleRestoreView.as_view(),
        name="blog-article-restore",
    ),
    path(
        "blog/articles/<slug:slug>/assign-moderator/",
        ArticleAssignModeratorView.as_view(),
        name="blog-article-assign-moderator",
    ),
    path(
        "blog/articles/<slug:slug>/approve/",
        ArticleApproveView.as_view(),
        name="blog-article-approve",
    ),
    path(
        "blog/articles/<slug:slug>/reject/", ArticleRejectView.as_view(), name="blog-article-reject"
    ),
]
