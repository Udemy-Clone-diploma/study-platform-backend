from urllib.parse import urlencode

from rest_framework.request import Request

from apps.common.cache import (
    build_cache_key,
    bump_namespace_generation,
    namespace_generation,
)

TOP_REVIEWS_CACHE_NAMESPACE = "top-reviews"
COURSE_REVIEWS_CACHE_NAMESPACE = "course-reviews"
COURSE_REVIEWS_GLOBAL_GENERATION_NAMESPACE = "course-reviews-global"
COURSE_REVIEWS_COURSE_GENERATION_NAMESPACE = "course-reviews-course"


def _request_origin(request: Request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def _canonical_query_string(request: Request) -> str:
    pairs = sorted(
        (key, value)
        for key in request.query_params
        for value in request.query_params.getlist(key)
    )
    return urlencode(pairs)


def top_reviews_cache_key(request: Request, limit: int) -> str:
    generation = namespace_generation(TOP_REVIEWS_CACHE_NAMESPACE)
    return build_cache_key(
        TOP_REVIEWS_CACHE_NAMESPACE,
        generation,
        _request_origin(request),
        limit,
    )


def course_reviews_cache_key(
    request: Request,
    *,
    course_id: int,
) -> str:
    global_generation = namespace_generation(
        COURSE_REVIEWS_GLOBAL_GENERATION_NAMESPACE,
    )
    course_generation = namespace_generation(
        COURSE_REVIEWS_COURSE_GENERATION_NAMESPACE,
        course_id,
    )
    return build_cache_key(
        COURSE_REVIEWS_CACHE_NAMESPACE,
        global_generation,
        course_generation,
        _request_origin(request),
        course_id,
        _canonical_query_string(request),
    )


def invalidate_top_reviews() -> None:
    bump_namespace_generation(TOP_REVIEWS_CACHE_NAMESPACE)


def invalidate_course_reviews(course_id: int) -> None:
    bump_namespace_generation(
        COURSE_REVIEWS_COURSE_GENERATION_NAMESPACE,
        course_id,
    )


def invalidate_all_course_reviews() -> None:
    bump_namespace_generation(COURSE_REVIEWS_GLOBAL_GENERATION_NAMESPACE)
