from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.reviews.models import Review
from apps.reviews.services import ReviewService
from apps.reviews.tests._factories import make_student


class TopReviewsCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        _, teacher = make_teacher(email="top-review-teacher@example.com")
        self.course = make_course(
            teacher,
            slug="top-review-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.student, _ = make_student(email="top-review-student@example.com")
        self.review = Review.objects.create(
            course=self.course,
            student=self.student,
            rating=5,
            text="Excellent",
        )
        cache.clear()
        self.url = reverse("top-reviews")

    def test_reuses_cached_response(self):
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch.object(
            ReviewService,
            "get_top_reviews",
            side_effect=AssertionError("top reviews should come from cache"),
        ):
            second = self.client.get(self.url)

        self.assertEqual(second.data[0]["text"], "Excellent")

    def test_review_change_invalidates_cache(self):
        self.client.get(self.url)

        with self.captureOnCommitCallbacks(execute=True):
            self.review.text = "Updated"
            self.review.save(update_fields=["text"])

        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["text"], "Updated")
