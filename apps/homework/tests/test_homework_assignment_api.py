from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Module
from apps.homework.models import HomeworkAssignment


class HomeworkAssignmentApiTests(APITestCase):
    def setUp(self):
        self.teacher, teacher_profile = make_teacher()
        self.course = make_course(teacher_profile, slug="homework-course")
        self.module = Module.objects.create(
            course=self.course,
            title="Module 1",
            order=1,
        )
        self.url = reverse("homework-assignment-list", args=[self.course.slug])

    def test_course_owner_can_create_a_homework_draft(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Build a portfolio page",
                "description": "Create a responsive page and submit its URL.",
                "module": self.module.id,
                "due_at": "2026-07-01T12:00:00Z",
                "max_score": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = HomeworkAssignment.objects.get()
        self.assertEqual(assignment.course, self.course)
        self.assertEqual(assignment.module, self.module)
        self.assertEqual(assignment.created_by, self.teacher)
        self.assertEqual(assignment.status, HomeworkAssignment.StatusChoices.DRAFT)
        self.assertEqual(response.data["course_id"], self.course.id)

    def test_other_teacher_cannot_create_a_homework_draft(self):
        other_teacher, _ = make_teacher(email="other@example.com")
        self.client.force_authenticate(other_teacher)

        response = self.client.post(
            self.url,
            {"title": "Unauthorized", "description": "This must not be created."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(HomeworkAssignment.objects.exists())

    def test_max_score_must_be_positive(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {"title": "Invalid score", "description": "Test", "max_score": 0},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_score", response.data)
