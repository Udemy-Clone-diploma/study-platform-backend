from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import TeacherProfile

from ._factories import make_user


def _make_teacher(email, *, rating="0.00", first_name="", last_name="", **user_overrides):
    user = make_user(role="teacher", email=email, first_name=first_name, last_name=last_name, **user_overrides)
    profile = TeacherProfile.objects.create(user=user, rating=Decimal(rating))
    return user, profile


class TopTeachersEndpointTests(APITestCase):
    """GET /users/top-teachers/ returns a raw list ordered by rating, capped by ?limit."""

    def test_returns_raw_list_not_paginated(self):
        response = self.client.get(reverse("top-teachers"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_orders_by_rating_descending(self):
        _make_teacher("low@example.com", rating="3.00", first_name="Low", last_name="X")
        _make_teacher("high@example.com", rating="4.50", first_name="High", last_name="Y")
        _make_teacher("mid@example.com", rating="3.80", first_name="Mid", last_name="Z")

        response = self.client.get(reverse("top-teachers"))

        names = [t["name"] for t in response.data]
        self.assertEqual(names, ["High Y", "Mid Z", "Low X"])

    def test_excludes_deleted_blocked_and_unverified(self):
        _make_teacher("good@example.com", rating="4.00", first_name="Good", last_name="T")
        _make_teacher(
            "deleted@example.com",
            rating="5.00",
            first_name="Deleted",
            last_name="T",
            is_deleted=True,
        )
        _make_teacher(
            "blocked@example.com",
            rating="5.00",
            first_name="Blocked",
            last_name="T",
            is_blocked=True,
        )
        _make_teacher(
            "unverified@example.com",
            rating="5.00",
            first_name="Unverif",
            last_name="T",
            verified=False,
        )

        response = self.client.get(reverse("top-teachers"))

        names = [t["name"] for t in response.data]
        self.assertEqual(names, ["Good T"])

    def test_limit_param_caps_results(self):
        for i in range(5):
            _make_teacher(
                f"t{i}@example.com",
                rating=f"{4 + i * 0.1:.2f}",
                first_name=f"T{i}",
                last_name="X",
            )

        response = self.client.get(reverse("top-teachers"), {"limit": 2})

        self.assertEqual(len(response.data), 2)

    def test_invalid_limit_returns_400(self):
        response = self.client.get(reverse("top-teachers"), {"limit": "abc"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", response.data)

    def test_serializer_payload_shape(self):
        _make_teacher(
            "shape@example.com",
            rating="4.20",
            first_name="Sha",
            last_name="Pe",
        )

        response = self.client.get(reverse("top-teachers"))

        teacher = response.data[0]
        for key in ("id", "name", "avatar", "specialization", "experience", "rating"):
            self.assertIn(key, teacher)
        self.assertEqual(teacher["name"], "Sha Pe")
