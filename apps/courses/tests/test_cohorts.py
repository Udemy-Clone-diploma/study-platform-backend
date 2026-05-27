from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Cohort, Course

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

    def test_anonymous_can_list_cohorts(self):
        response = self.client.get(
            reverse("cohorts-list", args=[self.published.slug])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


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
            "hours_per_week_min": 5,
            "hours_per_week_max": 10,
            "delivery_mode": Cohort.DeliveryModeChoices.GROUP,
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

    def test_hours_min_must_be_le_max(self):
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.post(
            reverse("cohorts-list", args=[self.course.slug]),
            self._payload(hours_per_week_min=20, hours_per_week_max=10),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("hours_per_week_min", response.data)

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
        response = self.client.delete(
            reverse("cohorts-detail", args=[self.course.slug, cohort.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Cohort.objects.filter(pk=cohort.pk).exists())
