from rest_framework.request import Request

from apps.common.cache import (
    build_versioned_cache_key,
    bump_namespace_generation,
)

PUBLIC_USER_PROFILE_CACHE_NAMESPACE = "public-user-profiles"
PUBLIC_TOP_TEACHERS_CACHE_NAMESPACE = "public-top-teachers"


def _request_origin(request: Request) -> str:
    return request.build_absolute_uri("/").rstrip("/")


def public_user_profile_cache_key(request: Request, target_user_id: int) -> str:
    viewer = request.user
    return build_versioned_cache_key(
        PUBLIC_USER_PROFILE_CACHE_NAMESPACE,
        "detail",
        _request_origin(request),
        viewer.pk,
        viewer.role,
        target_user_id,
        scope=(target_user_id,),
    )


def invalidate_public_user_profile(user_id: int) -> None:
    bump_namespace_generation(
        PUBLIC_USER_PROFILE_CACHE_NAMESPACE,
        user_id,
    )


def public_top_teachers_cache_key(request: Request, limit: int) -> str:
    return build_versioned_cache_key(
        PUBLIC_TOP_TEACHERS_CACHE_NAMESPACE,
        "list",
        _request_origin(request),
        limit,
    )


def invalidate_public_top_teachers() -> None:
    bump_namespace_generation(PUBLIC_TOP_TEACHERS_CACHE_NAMESPACE)
