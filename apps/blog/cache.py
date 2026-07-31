from urllib.parse import urlencode

from rest_framework.request import Request

from apps.common.cache import (
    build_versioned_cache_key,
    bump_namespace_generation,
    namespace_generation,
)

PUBLIC_ARTICLE_LIST_CACHE_NAMESPACE = "public-article-list"
PUBLIC_ARTICLE_DETAIL_CACHE_NAMESPACE = "public-article-detail"
PUBLIC_BLOG_CATEGORY_CACHE_NAMESPACE = "public-blog-categories"


def _request_origin(request: Request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def _public_article_query(request: Request) -> str:
    pairs = []
    for key in ("category", "search"):
        for value in request.query_params.getlist(key):
            pairs.append((key, value))
    return urlencode(sorted(pairs))


def public_article_list_cache_key(request: Request) -> str:
    return build_versioned_cache_key(
        PUBLIC_ARTICLE_LIST_CACHE_NAMESPACE,
        _request_origin(request),
        _public_article_query(request),
    )


def public_article_detail_cache_key(
    request: Request,
    *,
    article_id: int,
    slug: str,
) -> str:
    global_generation = namespace_generation(
        PUBLIC_ARTICLE_DETAIL_CACHE_NAMESPACE,
    )
    return build_versioned_cache_key(
        PUBLIC_ARTICLE_DETAIL_CACHE_NAMESPACE,
        global_generation,
        _request_origin(request),
        article_id,
        slug,
        scope=(article_id,),
    )


def public_blog_categories_cache_key(request: Request) -> str:
    return build_versioned_cache_key(
        PUBLIC_BLOG_CATEGORY_CACHE_NAMESPACE,
        _request_origin(request),
    )


def invalidate_public_article_lists() -> None:
    bump_namespace_generation(PUBLIC_ARTICLE_LIST_CACHE_NAMESPACE)


def invalidate_public_article_detail(article_id: int) -> None:
    bump_namespace_generation(
        PUBLIC_ARTICLE_DETAIL_CACHE_NAMESPACE,
        article_id,
    )


def invalidate_all_public_article_details() -> None:
    bump_namespace_generation(PUBLIC_ARTICLE_DETAIL_CACHE_NAMESPACE)


def invalidate_public_blog_categories() -> None:
    bump_namespace_generation(PUBLIC_BLOG_CATEGORY_CACHE_NAMESPACE)
