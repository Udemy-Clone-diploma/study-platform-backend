from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.courses.models import Course
from apps.reviews.exceptions import NotEnrolledError, ReviewAlreadyExistsError
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer
from apps.reviews.services import ReviewService


@extend_schema(tags=["Reviews"])
class CourseReviewsView(ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _get_course(self) -> Course:
        course = Course.objects.filter(
            slug=self.kwargs["slug"],
            status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")
        return course

    def get_queryset(self):
        return (
            Review.objects.filter(course=self._get_course())
            .select_related("student")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        course = self._get_course()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            review = ReviewService.create_review(
                request.user,
                course,
                rating=serializer.validated_data["rating"],
                text=serializer.validated_data.get("text", ""),
            )
        except NotEnrolledError:
            return Response(
                {"detail": "Only enrolled students can review this course."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ReviewAlreadyExistsError:
            return Response(
                {"detail": "You have already reviewed this course."},
                status=status.HTTP_409_CONFLICT,
            )

        out = self.get_serializer(review)
        return Response(out.data, status=status.HTTP_201_CREATED)
