from apps.courses.exceptions import CourseNotFoundError
from apps.courses.models import Course
from apps.users.models import StudentProfile


class WishlistService:
    @staticmethod
    def get_wishlisted_courses(student_profile: StudentProfile):
        return (
            student_profile.wishlisted_courses
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )

    @staticmethod
    def toggle(student_profile: StudentProfile, slug: str) -> bool:
        try:
            course = Course.objects.get(
                slug=slug,
                status=Course.StatusChoices.PUBLISHED,
            )
        except Course.DoesNotExist:
            raise CourseNotFoundError(slug)

        wishlist = student_profile.wishlisted_courses
        if wishlist.filter(pk=course.pk).exists():
            wishlist.remove(course)
            return False
        wishlist.add(course)
        return True
