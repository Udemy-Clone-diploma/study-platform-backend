from apps.courses.exceptions import CourseNotFoundError
from apps.courses.models import Course
from apps.courses.serializers import CourseListSerializer
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
    def serialize_courses(queryset, request) -> list:
        return CourseListSerializer(queryset, many=True, context={"request": request}).data

    @staticmethod
    def toggle(student_profile: StudentProfile, slug: str) -> bool:
        try:
            course = Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            raise CourseNotFoundError(slug)

        wishlist = student_profile.wishlisted_courses
        if wishlist.filter(pk=course.pk).exists():
            wishlist.remove(course)
            return False
        wishlist.add(course)
        return True
