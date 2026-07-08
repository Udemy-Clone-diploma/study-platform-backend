from django.db import IntegrityError, transaction

from apps.courses.models import Course
from apps.enrollments.exceptions import ActiveEnrollmentRequiredError
from apps.enrollments.services import ProgressService
from apps.reviews.constants import DEFAULT_TOP_REVIEWS_LIMIT
from apps.reviews.exceptions import (
    NotEnrolledError,
    ReviewAlreadyExistsError,
    ReviewEligibilityNotMetError,
)
from apps.reviews.models import Review
from apps.reviews.serializers import TopReviewSerializer
from apps.users.models import User


class ReviewService:
    @classmethod
    def get_top_reviews(
        cls,
        limit: int = DEFAULT_TOP_REVIEWS_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        """Highest-rated reviews with written feedback, for platform-wide surfaces like the homepage."""
        reviews = (
            Review.objects.filter(course__status=Course.StatusChoices.PUBLISHED)
            .exclude(text="")
            .select_related("student", "course")
            .order_by("-rating", "-created_at")[:limit]
        )
        return TopReviewSerializer(reviews, many=True, context=context or {}).data

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
        try:
            enrollment = ProgressService.get_active_enrollment(user, course)
        except ActiveEnrollmentRequiredError as exc:
            raise NotEnrolledError from exc

        if not ProgressService.is_eligible_to_review(enrollment, course):
            raise ReviewEligibilityNotMetError

        try:
            return Review.objects.create(
                course=course, student=user, rating=rating, text=text,
            )
        except IntegrityError as exc:
            raise ReviewAlreadyExistsError from exc
