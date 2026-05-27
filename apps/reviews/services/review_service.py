from django.db import IntegrityError, transaction

from apps.courses.models import Course
from apps.enrollments.services import EnrollmentService
from apps.reviews.exceptions import NotEnrolledError, ReviewAlreadyExistsError
from apps.reviews.models import Review
from apps.users.models import User


class ReviewService:
    @classmethod
    @transaction.atomic
    def create_review(
        cls,
        user: User,
        course: Course,
        *,
        rating: int,
        text: str,
    ) -> Review:
        if not EnrollmentService.is_enrolled(user, course):
            raise NotEnrolledError

        try:
            return Review.objects.create(
                course=course, student=user, rating=rating, text=text,
            )
        except IntegrityError as exc:
            raise ReviewAlreadyExistsError from exc
