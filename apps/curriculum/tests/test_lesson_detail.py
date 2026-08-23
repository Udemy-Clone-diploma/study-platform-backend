from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, LessonItem, Module, Question, Test
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile, User


def _make_student(email="lesson_student@example.com"):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        role=User.RoleChoices.STUDENT,
    )
    profile = StudentProfile.objects.create(user=user)
    return user, profile


class LessonDetailAccessTests(APITestCase):
    def setUp(self):
        self.owner_user, self.owner_profile = make_teacher(email="lesson_owner@example.com")
        _, self.other_profile = make_teacher(email="lesson_other@example.com")
        self.course = make_course(
            self.owner_profile,
            slug="lesson-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.draft = make_course(
            self.owner_profile,
            title="Draft",
            slug="lesson-draft",
            status=Course.StatusChoices.DRAFT,
        )
        self.module = Module.objects.create(
            course=self.course,
            title="M1",
            order=1,
        )
        self.preview_lesson = Lesson.objects.create(
            module=self.module,
            title="Preview",
            order=1,
            is_preview=True,
        )
        self.locked_lesson = Lesson.objects.create(
            module=self.module,
            title="Locked",
            order=2,
            is_preview=False,
        )
        cache.clear()

    def _url(self, course_slug, lesson_id):
        return reverse(
            "course-lesson-detail",
            args=[course_slug, lesson_id],
        )

    def test_anonymous_can_view_preview_lesson(self):
        response = self.client.get(self._url(self.course.slug, self.preview_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Preview")

    def test_anonymous_cannot_view_locked_lesson(self):
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enrolled_student_can_view_locked_lesson(self):
        student_user, student_profile = _make_student()
        Enrollment.objects.create(student_profile=student_profile, course=self.course)
        self.client.force_authenticate(user=student_user)
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_enrolled_student_cannot_view_locked_lesson(self):
        student_user, _ = _make_student(email="non_enrolled@example.com")
        self.client.force_authenticate(user=student_user)
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_teacher_can_view_locked_lesson(self):
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_teacher_cannot_view_locked_lesson(self):
        self.client.force_authenticate(user=self.other_profile.user)
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_any_locked_lesson(self):
        admin = User.objects.create_user(
            email="lesson_admin@example.com",
            password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get(self._url(self.course.slug, self.locked_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_lesson_in_draft_course_returns_404(self):
        draft_module = Module.objects.create(course=self.draft, title="Draft M", order=1)
        draft_lesson = Lesson.objects.create(
            module=draft_module,
            title="Hidden",
            order=1,
            is_preview=True,
        )
        response = self.client.get(self._url(self.draft.slug, draft_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lesson_in_different_course_returns_404(self):
        other_course = make_course(
            self.other_profile,
            title="Other",
            slug="other-course-lesson",
            status=Course.StatusChoices.PUBLISHED,
        )
        response = self.client.get(self._url(other_course.slug, self.preview_lesson.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reuses_cached_lesson_payload(self):
        url = self._url(self.course.slug, self.preview_lesson.pk)
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch(
            "apps.curriculum.views.LessonDetailView.LessonSerializer.to_representation",
            side_effect=AssertionError("lesson should come from cache"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.data["title"], "Preview")

    def test_lesson_change_invalidates_cached_payload(self):
        url = self._url(self.course.slug, self.preview_lesson.pk)
        self.client.get(url)

        with self.captureOnCommitCallbacks(execute=True):
            self.preview_lesson.title = "Updated preview"
            self.preview_lesson.save(update_fields=["title"])

        response = self.client.get(url)
        self.assertEqual(response.data["title"], "Updated preview")

    def test_cached_lesson_is_separated_by_viewer_permissions(self):
        test = Test.objects.create(
            module=self.module,
            title="Visibility test",
            passing_score=70,
            order=1,
        )
        Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.SINGLE_CHOICE,
            text="Choose",
            options=["secret answer", "wrong"],
            correct_indices=[0],
            order=1,
        )
        LessonItem.objects.create(
            lesson=self.locked_lesson,
            item_type=LessonItem.ItemType.TEST,
            test=test,
            order=1,
        )
        student_user, student_profile = _make_student(
            email="lesson-cache-student@example.com",
        )
        Enrollment.objects.create(
            student_profile=student_profile,
            course=self.course,
        )
        cache.clear()
        url = self._url(self.course.slug, self.locked_lesson.pk)

        self.client.force_authenticate(student_user)
        student_response = self.client.get(url)
        student_question = student_response.data["items"][0]["test"]["questions"][0]
        self.assertNotIn("correct_indices", student_question)

        self.client.force_authenticate(self.owner_user)
        teacher_response = self.client.get(url)
        teacher_question = teacher_response.data["items"][0]["test"]["questions"][0]
        self.assertEqual(teacher_question["correct_indices"], [0])

    def test_cached_lesson_does_not_preserve_revoked_access(self):
        student_user, student_profile = _make_student(
            email="lesson-revoked-student@example.com",
        )
        enrollment = Enrollment.objects.create(
            student_profile=student_profile,
            course=self.course,
        )
        self.client.force_authenticate(student_user)
        url = self._url(self.course.slug, self.locked_lesson.pk)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

        with self.captureOnCommitCallbacks(execute=True):
            enrollment.delete()

        self.assertEqual(
            self.client.get(url).status_code,
            status.HTTP_403_FORBIDDEN,
        )
