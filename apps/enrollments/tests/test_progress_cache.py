from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.enrollments.services import ProgressService
from apps.enrollments.tests._factories import make_student


class CourseProgressCacheTests(APITestCase):
    def setUp(self):
        _, teacher = make_teacher(email="progress-cache-teacher@example.com")
        self.course = make_course(
            teacher,
            slug="progress-cache-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        module = Module.objects.create(course=self.course, title="Module", order=1)
        self.lesson = Lesson.objects.create(
            module=module,
            title="Opened lesson",
            order=1,
        )
        self.user, self.student_profile = make_student(
            email="progress-cache-student@example.com",
        )
        self.enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.client.force_authenticate(self.user)
        self.progress_url = reverse("course-progress", args=[self.course.slug])
        cache.clear()

    def test_reuses_cached_progress_payload(self):
        first = self.client.get(self.progress_url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch.object(
            ProgressService,
            "get_course_progress",
            side_effect=AssertionError("progress should come from cache"),
        ):
            second = self.client.get(self.progress_url)

        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertIsNone(second.data["last_lesson_id"])

    def test_opening_lesson_invalidates_progress_cache(self):
        first = self.client.get(self.progress_url)
        self.assertIsNone(first.data["last_lesson_id"])

        with self.captureOnCommitCallbacks(execute=True):
            opened = self.client.post(
                reverse(
                    "lesson-open",
                    args=[self.course.slug, self.lesson.pk],
                ),
            )
        self.assertEqual(opened.status_code, status.HTTP_204_NO_CONTENT)

        second = self.client.get(self.progress_url)
        self.assertEqual(second.data["last_lesson_id"], self.lesson.pk)
        self.assertIsNotNone(second.data["last_opened_at"])

    def test_cache_does_not_preserve_revoked_enrollment_access(self):
        self.assertEqual(
            self.client.get(self.progress_url).status_code,
            status.HTTP_200_OK,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.enrollment.access_status = Enrollment.AccessStatusChoices.REVOKED
            self.enrollment.save(update_fields=["access_status"])

        self.assertEqual(
            self.client.get(self.progress_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )
