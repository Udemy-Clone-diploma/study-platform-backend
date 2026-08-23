from rest_framework.request import Request

from apps.common.cache import (
    build_cache_key,
    bump_namespace_generation,
    namespace_generation,
)

LESSON_DETAIL_CACHE_NAMESPACE = "lesson-details"
LESSON_CONTENT_GENERATION_NAMESPACE = "lesson-content"
LESSON_VIEWER_GENERATION_NAMESPACE = "lesson-viewer"


def _request_origin(request: Request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def _viewer_identity(request: Request) -> tuple[object, str]:
    user = request.user
    if not user or not user.is_authenticated:
        return "anonymous", "anonymous"
    return user.pk, user.role


def lesson_detail_cache_key(
    request: Request,
    *,
    course_slug: str,
    lesson_id: int,
    access_level: str,
) -> str:
    viewer_id, viewer_role = _viewer_identity(request)
    content_generation = namespace_generation(
        LESSON_CONTENT_GENERATION_NAMESPACE,
        lesson_id,
    )
    viewer_generation = namespace_generation(
        LESSON_VIEWER_GENERATION_NAMESPACE,
        lesson_id,
        viewer_id,
    )
    return build_cache_key(
        LESSON_DETAIL_CACHE_NAMESPACE,
        content_generation,
        viewer_generation,
        _request_origin(request),
        course_slug,
        lesson_id,
        viewer_id,
        viewer_role,
        access_level,
    )


def invalidate_lesson_content(lesson_id: int) -> None:
    bump_namespace_generation(
        LESSON_CONTENT_GENERATION_NAMESPACE,
        lesson_id,
    )


def invalidate_lesson_for_user(lesson_id: int, user_id: int) -> None:
    bump_namespace_generation(
        LESSON_VIEWER_GENERATION_NAMESPACE,
        lesson_id,
        user_id,
    )
