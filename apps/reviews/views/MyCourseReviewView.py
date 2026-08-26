from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.courses.models import Course
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer
from apps.reviews.services import ReviewService


@extend_schema(tags=["Reviews"])
class MyCourseReviewView(RetrieveUpdateAPIView):
    """The authenticated student's own review for a course.

    GET 404s when they haven't reviewed it yet, so the frontend can
    distinguish "no review" from a real error and offer to leave one.
    PATCH/PUT lets them edit an existing review at any time -- editing
    doesn't re-check enrollment/eligibility, since leaving the review in
    the first place already proved they'd earned the right to.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        course = Course.objects.filter(
            slug=self.kwargs["slug"],
            status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")

        review = (
            Review.objects.filter(course=course, student=self.request.user)
            .select_related("student")
            .first()
        )
        if review is None:
            raise NotFound("You have not reviewed this course yet.")
        return review

    def perform_update(self, serializer):
        ReviewService.update_review(
            serializer.instance,
            rating=serializer.validated_data.get("rating", serializer.instance.rating),
            text=serializer.validated_data.get("text", serializer.instance.text),
        )
