from apps.common.cache import (
    build_cache_key,
    bump_namespace_generation,
    namespace_generation,
)

COURSE_PROGRESS_CACHE_NAMESPACE = "course-progress"
COURSE_PROGRESS_CONTENT_GENERATION_NAMESPACE = "course-progress-content"
COURSE_PROGRESS_USER_GENERATION_NAMESPACE = "course-progress-user"


def course_progress_cache_key(
    *,
    user_id: int,
    course_id: int,
) -> str:
    content_generation = namespace_generation(
        COURSE_PROGRESS_CONTENT_GENERATION_NAMESPACE,
        course_id,
    )
    user_generation = namespace_generation(
        COURSE_PROGRESS_USER_GENERATION_NAMESPACE,
        user_id,
        course_id,
    )
    return build_cache_key(
        COURSE_PROGRESS_CACHE_NAMESPACE,
        content_generation,
        user_generation,
        user_id,
        course_id,
    )


def invalidate_course_progress_for_user(user_id: int, course_id: int) -> None:
    bump_namespace_generation(
        COURSE_PROGRESS_USER_GENERATION_NAMESPACE,
        user_id,
        course_id,
    )


def invalidate_course_progress_for_course(course_id: int) -> None:
    bump_namespace_generation(
        COURSE_PROGRESS_CONTENT_GENERATION_NAMESPACE,
        course_id,
    )
