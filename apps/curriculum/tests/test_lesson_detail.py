from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, Module
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
            course=self.course, title="M1", order=1,
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

    def _url(self, course_slug, lesson_id):
        return reverse(
            "course-lesson-detail", args=[course_slug, lesson_id],
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
            module=draft_module, title="Hidden", order=1, is_preview=True,
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
