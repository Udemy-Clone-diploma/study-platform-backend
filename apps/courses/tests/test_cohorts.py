from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Cohort, Course
from apps.enrollments.tests._factories import make_student

from ._factories import make_cohort, make_course, make_teacher


class CohortReadTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher(email="cohort_teacher@example.com")
        self.published = make_course(
            self.teacher_profile,
            slug="cohort-published",
            status=Course.StatusChoices.PUBLISHED,
        )
        make_cohort(self.published, duration_months=3)
        make_cohort(self.published, duration_months=6)

    def test_anonymous_cannot_list_management_cohorts(self):
        response = self.client.get(reverse("cohorts-list", args=[self.published.slug]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_course_owner_can_list_management_cohorts(self):
        self.client.force_authenticate(user=self.teacher_profile.user)
        response = self.client.get(reverse("cohorts-list", args=[self.published.slug]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_student_cannot_list_management_cohorts(self):
        student, _ = make_student(email="cohort_student@example.com")
        self.client.force_authenticate(user=student)

        response = self.client.get(reverse("cohorts-list", args=[self.published.slug]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CohortWriteTests(APITestCase):
    def setUp(self):
        _, self.owner_profile = make_teacher(email="cohort_owner@example.com")
        _, self.other_profile = make_teacher(email="cohort_other@example.com")
        self.course = make_course(
            self.owner_profile,
            slug="cohort-course",
            status=Course.StatusChoices.PUBLISHED,
        )

    def _payload(self, **overrides):
        data = {
            "duration_months": 4,
            "hours_per_week": 8,
        }
        data.update(overrides)
        return data

    def test_other_teacher_cannot_create(self):
        self.client.force_authenticate(user=self.other_profile.user)
        response = self.client.post(
            reverse("cohorts-list", args=[self.course.slug]),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_create(self):
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.post(
            reverse("cohorts-list", args=[self.course.slug]),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_can_patch(self):
        cohort = make_cohort(self.course, duration_months=2)
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.patch(
            reverse("cohorts-detail", args=[self.course.slug, cohort.pk]),
            {"duration_months": 6},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cohort.refresh_from_db()
        self.assertEqual(cohort.duration_months, 6)

    def test_owner_can_delete(self):
        cohort = make_cohort(self.course)
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.delete(reverse("cohorts-detail", args=[self.course.slug, cohort.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Cohort.objects.filter(pk=cohort.pk).exists())
