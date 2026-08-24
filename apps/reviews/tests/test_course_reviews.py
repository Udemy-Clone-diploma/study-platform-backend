from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import CourseCompletion, Enrollment, LessonCompletion
from apps.enrollments.services import ProgressService
from apps.reviews.models import Review
from apps.reviews.tests._factories import make_student
from apps.reviews.views.CourseReviewsView import CourseReviewsView


class CourseReviewsReadTests(APITestCase):
    def setUp(self):
        cache.clear()
        _, self.teacher_profile = make_teacher(email="reviews_teacher@example.com")
        self.published = make_course(
            self.teacher_profile,
            slug="reviews-published",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.draft = make_course(
            self.teacher_profile,
            title="Draft Reviews",
            slug="reviews-draft",
            status=Course.StatusChoices.DRAFT,
        )

    def test_anonymous_can_list_reviews_for_published(self):
        response = self.client.get(reverse("course-reviews", args=[self.published.slug]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unpublished_course_returns_404(self):
        response = self.client.get(reverse("course-reviews", args=[self.draft.slug]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reuses_cached_paginated_response(self):
        student, _ = make_student(email="reviews_cached_student@example.com")
        Review.objects.create(
            course=self.published,
            student=student,
            rating=5,
            text="Cached review",
        )
        url = reverse("course-reviews", args=[self.published.slug])
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch.object(
            CourseReviewsView,
            "get_queryset",
            side_effect=AssertionError("reviews should come from cache"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.data["results"][0]["text"], "Cached review")
        self.assertEqual(second.data["results"][0]["student"]["role"], "Student")

    def test_review_change_invalidates_course_cache(self):
        student, _ = make_student(email="reviews_changed_student@example.com")
        review = Review.objects.create(
            course=self.published,
            student=student,
            rating=4,
            text="Before",
        )
        url = reverse("course-reviews", args=[self.published.slug])
        self.client.get(url)

        with self.captureOnCommitCallbacks(execute=True):
            review.text = "After"
            review.save(update_fields=["text"])

        response = self.client.get(url)
        self.assertEqual(response.data["results"][0]["text"], "After")


class CourseReviewsWriteTests(APITestCase):
    def setUp(self):
        cache.clear()
        _, self.teacher_profile = make_teacher(email="rw_teacher@example.com")
        self.course = make_course(
            self.teacher_profile,
            slug="rw-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.module = Module.objects.create(course=self.course, title="M1", order=1)
        self.lesson = Lesson.objects.create(module=self.module, title="L1", order=1)
        self.student_user, self.student_profile = make_student(email="rw_student@example.com")
        self.outsider_user, _ = make_student(email="rw_outsider@example.com")

    def _enroll(self, student_profile, *, complete_lessons: bool = True):
        enrollment = Enrollment.objects.create(
            student_profile=student_profile,
            course=self.course,
        )
        if complete_lessons:
            LessonCompletion.objects.create(enrollment=enrollment, lesson=self.lesson)
        return enrollment

    def test_anonymous_cannot_post(self):
        response = self.client.post(
            reverse("course-reviews", args=[self.course.slug]),
            {"rating": 5, "text": "Great"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_enrolled_student_cannot_post(self):
        self.client.force_authenticate(user=self.outsider_user)
        response = self.client.post(
            reverse("course-reviews", args=[self.course.slug]),
            {"rating": 4, "text": "Not enrolled"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enrolled_student_can_post(self):
        self._enroll(self.student_profile)
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            reverse("course-reviews", args=[self.course.slug]),
            {"rating": 5, "text": "Loved it"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["text"], "Loved it")

    def test_duplicate_review_returns_409(self):
        self._enroll(self.student_profile)
        Review.objects.create(
            course=self.course,
            student=self.student_user,
            rating=4,
            text="ok",
        )
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            reverse("course-reviews", args=[self.course.slug]),
            {"rating": 5, "text": "again"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_review_signal_updates_course_rating(self):
        self._enroll(self.student_profile)
        other_user, other_profile = make_student(email="rw_other@example.com")
        self._other_enrollment = Enrollment.objects.create(
            student_profile=other_profile,
            course=self.course,
        )

        Review.objects.create(
            course=self.course,
            student=self.student_user,
            rating=5,
            text="",
        )
        Review.objects.create(
            course=self.course,
            student=other_user,
            rating=3,
            text="",
        )

        self.course.refresh_from_db()
        self.assertEqual(self.course.rating_count, 2)
        self.assertEqual(self.course.rating_avg, Decimal("4.00"))

    def test_review_delete_recomputes_rating(self):
        self._enroll(self.student_profile)
        review = Review.objects.create(
            course=self.course,
            student=self.student_user,
            rating=5,
            text="",
        )

        self.course.refresh_from_db()
        self.assertEqual(self.course.rating_count, 1)

        review.delete()

        self.course.refresh_from_db()
        self.assertEqual(self.course.rating_count, 0)
        self.assertEqual(self.course.rating_avg, Decimal("0.00"))

    def test_teacher_completed_course_with_no_lessons_is_reviewable(self):
        """Group/individual courses can have zero curriculum lessons (teacher
        teaches live), so the lesson-progress eligibility check can never
        pass for them -- a teacher-marked completion must be enough on its own."""
        no_lesson_course = make_course(
            self.teacher_profile,
            slug="rw-course-no-lessons",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.assertEqual(no_lesson_course.lessons_count, 0)
        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=no_lesson_course,
        )
        CourseCompletion.objects.create(
            student_profile=self.student_profile,
            course=no_lesson_course,
            title=no_lesson_course.title,
            teacher_name="Teacher",
            level=no_lesson_course.level,
            progress_percent=100,
            started_at=timezone.now(),
        )

        self.assertTrue(ProgressService.is_eligible_to_review(enrollment, no_lesson_course))

        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            reverse("course-reviews", args=[no_lesson_course.slug]),
            {"rating": 5, "text": "Great live sessions"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class MyCourseReviewTests(APITestCase):
    def setUp(self):
        cache.clear()
        _, self.teacher_profile = make_teacher(email="mine_teacher@example.com")
        self.course = make_course(
            self.teacher_profile,
            slug="mine-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.student_user, self.student_profile = make_student(email="mine_student@example.com")

    def test_anonymous_cannot_fetch(self):
        response = self.client.get(reverse("course-reviews-mine", args=[self.course.slug]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_404_when_no_review_yet(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(reverse("course-reviews-mine", args=[self.course.slug]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_own_review(self):
        Review.objects.create(
            course=self.course,
            student=self.student_user,
            rating=4,
            text="Mine",
        )
        other_user, _ = make_student(email="mine_other@example.com")
        Review.objects.create(course=self.course, student=other_user, rating=1, text="Not mine")

        self.client.force_authenticate(user=self.student_user)
        response = self.client.get(reverse("course-reviews-mine", args=[self.course.slug]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["text"], "Mine")
        self.assertEqual(response.data["rating"], 4)
