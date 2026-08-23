from django.db import IntegrityError, transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.courses.models import Course
from apps.enrollments.exceptions import ActiveEnrollmentRequiredError
from apps.enrollments.services import ProgressService
from apps.reviews.constants import DEFAULT_TOP_REVIEWS_LIMIT, REVIEW_MODERATION_REPORT_THRESHOLD
from apps.reviews.exceptions import (
    AlreadyReportedError,
    CannotReportOwnReviewError,
    NotEnrolledError,
    ReviewAlreadyAssignedError,
    ReviewAlreadyExistsError,
    ReviewEligibilityNotMetError,
    ReviewNotAssignedToModeratorError,
    ReviewsError,
)
from apps.reviews.models import Review, ReviewReport
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

    @classmethod
    @transaction.atomic
    def report_review(cls, user: User, review: Review, *, reason: str) -> ReviewReport:
        if review.student_id == user.id:
            raise CannotReportOwnReviewError
        try:
            report = ReviewReport.objects.create(review=review, reporter=user, reason=reason)
        except IntegrityError as exc:
            raise AlreadyReportedError from exc

        # A previously-approved review that gets a fresh report from someone new
        # deserves another look, so send it back to the shared unassigned queue
        # rather than letting it sit silently under "Approved" with a rising
        # count nobody's watching. (Rejected reviews are hidden/unreportable,
        # so this only ever applies to the approved outcome.)
        if review.moderation_status == Review.ModerationStatusChoices.APPROVED:
            review.moderation_status = ""
            review.moderator_profile = None
            review.moderation_assigned_at = None
            review.moderated_at = None
            review.save(
                update_fields=[
                    "moderation_status",
                    "moderator_profile",
                    "moderation_assigned_at",
                    "moderated_at",
                ]
            )

        return report

    @classmethod
    def get_reported_queryset(cls) -> QuerySet[Review]:
        """Reviews reported by enough distinct people to warrant moderator attention."""
        return (
            Review.all_objects.annotate(report_count=Count("reports"))
            .filter(report_count__gte=REVIEW_MODERATION_REPORT_THRESHOLD)
            .select_related("student", "course", "moderator_profile__user")
            .prefetch_related("reports__reporter")
        )

    @classmethod
    def get_unassigned_reported_queryset(cls) -> QuerySet[Review]:
        """The shared pool: reported reviews no moderator has claimed yet."""
        return cls.get_reported_queryset().filter(moderator_profile__isnull=True).order_by("created_at")

    @classmethod
    def get_my_reported_queryset(cls, moderator_profile) -> QuerySet[Review]:
        """Reported reviews the given moderator has claimed, at any resolution status."""
        return cls.get_reported_queryset().filter(moderator_profile=moderator_profile).order_by("-created_at")

    @classmethod
    @transaction.atomic
    def assign_moderator_self(cls, review: Review, moderator_profile) -> Review:
        if moderator_profile is None:
            raise ReviewsError("Authenticated user does not have a moderator profile.")
        if review.moderator_profile_id is not None:
            raise ReviewAlreadyAssignedError
        review.moderator_profile = moderator_profile
        review.moderation_status = Review.ModerationStatusChoices.PENDING
        review.moderation_assigned_at = timezone.now()
        review.moderated_at = None
        review.save(
            update_fields=[
                "moderator_profile",
                "moderation_status",
                "moderation_assigned_at",
                "moderated_at",
            ]
        )
        return review

    @classmethod
    def approve_reported_review(cls, review: Review, moderator_profile) -> Review:
        """Dismiss the reports: the review stays live as-is."""
        if review.moderator_profile_id != getattr(moderator_profile, "id", None):
            raise ReviewNotAssignedToModeratorError
        review.moderation_status = Review.ModerationStatusChoices.APPROVED
        review.moderated_at = timezone.now()
        review.save(update_fields=["moderation_status", "moderated_at"])
        return review

    @classmethod
    def reject_reported_review(cls, review: Review, moderator_profile) -> Review:
        """Uphold the reports: hide the review from public view."""
        if review.moderator_profile_id != getattr(moderator_profile, "id", None):
            raise ReviewNotAssignedToModeratorError
        review.moderation_status = Review.ModerationStatusChoices.REJECTED
        review.is_deleted = True
        review.moderated_at = timezone.now()
        review.save(update_fields=["moderation_status", "is_deleted", "moderated_at"])
        return review
