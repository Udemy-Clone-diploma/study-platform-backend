from urllib.parse import urlencode

from rest_framework.request import Request

from apps.common.cache import (
    build_versioned_cache_key,
    bump_namespace_generation,
)
from apps.common.i18n import resolve_locale

PUBLIC_COURSES_CACHE_NAMESPACE = "public-courses"
PUBLIC_CATEGORIES_CACHE_NAMESPACE = "public-categories"


def _request_origin(request: Request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def _canonical_query_string(request: Request) -> str:
    pairs = sorted(
        (key, value)
        for key in request.query_params
        for value in request.query_params.getlist(key)
    )
    return urlencode(pairs)


def public_course_list_cache_key(request: Request) -> str:
    return build_versioned_cache_key(
        PUBLIC_COURSES_CACHE_NAMESPACE,
        "list",
        _request_origin(request),
        _canonical_query_string(request),
    )


def public_course_detail_cache_key(request: Request, slug: str) -> str:
    return build_versioned_cache_key(
        PUBLIC_COURSES_CACHE_NAMESPACE,
        "detail",
        _request_origin(request),
        slug,
        resolve_locale(request),
    )


def public_new_courses_cache_key(request: Request, limit: int) -> str:
    return build_versioned_cache_key(
        PUBLIC_COURSES_CACHE_NAMESPACE,
        "new",
        _request_origin(request),
        limit,
        resolve_locale(request),
    )


def public_popular_courses_cache_key(request: Request, limit: int) -> str:
    return build_versioned_cache_key(
        PUBLIC_COURSES_CACHE_NAMESPACE,
        "popular",
        _request_origin(request),
        limit,
        resolve_locale(request),
    )


def public_category_list_cache_key(request: Request) -> str:
    return build_versioned_cache_key(
        PUBLIC_CATEGORIES_CACHE_NAMESPACE,
        "list",
        _request_origin(request),
        _canonical_query_string(request),
    )


def public_featured_categories_cache_key(request: Request, limit: int) -> str:
    return build_versioned_cache_key(
        PUBLIC_CATEGORIES_CACHE_NAMESPACE,
        "featured",
        _request_origin(request),
        limit,
        resolve_locale(request),
    )


def invalidate_public_courses() -> None:
    bump_namespace_generation(PUBLIC_COURSES_CACHE_NAMESPACE)


def invalidate_public_categories() -> None:
    bump_namespace_generation(PUBLIC_CATEGORIES_CACHE_NAMESPACE)


def invalidate_public_courses_and_categories() -> None:
    invalidate_public_courses()
    invalidate_public_categories()
