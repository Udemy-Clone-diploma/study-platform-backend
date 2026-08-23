from rest_framework.exceptions import NotFound, PermissionDenied

from apps.courses.models import Course
from apps.users.models import User


def get_course_for_request(view, slug: str) -> Course:
    """Resolve a Course by slug and enforce read visibility"""
    course = Course.all_objects.filter(slug=slug).select_related("teacher_profile__user").first()
    if course is None or course.is_deleted:
        raise NotFound("Course not found.")
    if not _can_view_course(view.request.user, course):
        raise NotFound("Course not found.")
    return course


def ensure_can_modify_course(user, course: Course) -> None:
    """Raises PermissionDenied if the user cannot manage course-scoped resources."""
    if not user or not user.is_authenticated:
        raise PermissionDenied()
    if user.role == User.RoleChoices.ADMINISTRATOR:
        return
    if user.role == User.RoleChoices.TEACHER and course.teacher_profile.user_id == user.id:
        return
    raise PermissionDenied("Only the course owner or an admin can modify this resource.")


def ensure_can_view_course_management(user, course: Course) -> None:
    """Allow full course-scoped management data only to trusted course roles."""
    if not user or not user.is_authenticated:
        raise PermissionDenied()
    if user.role in (
        User.RoleChoices.ADMINISTRATOR,
        User.RoleChoices.MODERATOR,
    ):
        return
    if user.role == User.RoleChoices.TEACHER and course.teacher_profile.user_id == user.id:
        return
    raise PermissionDenied(
        "Only the course owner, a moderator, or an admin can view this resource."
    )


def _can_view_course(user, course: Course) -> bool:
    if course.status == Course.StatusChoices.PUBLISHED:
        return True
    if not user or not user.is_authenticated:
        return False
    if user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR):
        return True
    return course.teacher_profile.user_id == user.id


def _get_dict(data, key: str) -> dict:
    val = data.get(key, {})
    return val if isinstance(val, dict) else {}


def _moderator_profile(user):
    return getattr(user, "moderator_profile", None)
