from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.courses.models import Course
from apps.reviews.cache import course_reviews_cache_key
from apps.reviews.exceptions import (
    NotEnrolledError,
    ReviewAlreadyExistsError,
    ReviewEligibilityNotMetError,
)
from apps.reviews.models import Review
from apps.reviews.serializers import ReviewSerializer
from apps.reviews.services import ReviewService


@extend_schema(tags=["Reviews"])
class CourseReviewsView(ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _get_course(self) -> Course:
        if hasattr(self, "_course"):
            return self._course
        course = Course.objects.filter(
            slug=self.kwargs["slug"],
            status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")
        self._course = course
        return course

    def get_queryset(self):
        return (
            Review.objects.filter(course=self._get_course())
            .select_related("student")
            .order_by("-created_at")
        )

    def list(self, request, *args, **kwargs):
        course = self._get_course()

        def build_payload():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data).data
            return self.get_serializer(queryset, many=True).data

        data = cache_get_or_set(
            course_reviews_cache_key(request, course_id=course.pk),
            build_payload,
            timeout=jittered_cache_timeout(
                settings.CACHE_DEFAULT_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(data)

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
        except ReviewEligibilityNotMetError:
            return Response(
                {
                    "detail": (
                        "Complete at least 30% of the course's lessons "
                        "before leaving a review."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except ReviewAlreadyExistsError:
            return Response(
                {"detail": "You have already reviewed this course."},
                status=status.HTTP_409_CONFLICT,
            )

        out = self.get_serializer(review)
        return Response(out.data, status=status.HTTP_201_CREATED)
