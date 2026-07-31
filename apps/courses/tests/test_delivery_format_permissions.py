from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course, CourseDeliveryFormat
from apps.enrollments.tests._factories import make_student

from ._factories import make_course, make_teacher


class DeliveryFormatReadPermissionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher(
            email="delivery-format-owner@example.com",
        )
        cls.course = make_course(
            cls.teacher_profile,
            slug="delivery-format-permissions",
            status=Course.StatusChoices.PUBLISHED,
        )
        CourseDeliveryFormat.objects.create(
            course=cls.course,
            format_type=CourseDeliveryFormat.FormatType.GROUP,
        )

    def test_anonymous_cannot_list_management_delivery_formats(self):
        response = self.client.get(
            reverse("delivery-formats-list", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_course_owner_can_list_management_delivery_formats(self):
        self.client.force_authenticate(user=self.teacher_profile.user)

        response = self.client.get(
            reverse("delivery-formats-list", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_list_management_delivery_formats(self):
        student, _ = make_student(email="delivery-format-student@example.com")
        self.client.force_authenticate(user=student)

        response = self.client.get(
            reverse("delivery-formats-list", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
