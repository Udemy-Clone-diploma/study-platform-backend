from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User

from ._factories import authenticate_as_admin, make_user


class UserListFilterTests(APITestCase):
    """GET /users/ supports search, role/status/is_blocked filters, and ordering."""

    def setUp(self):
        authenticate_as_admin(self.client)
        self.url = reverse("users-list")
        self.jane = make_user(
            role="student",
            email="jane@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        self.john = make_user(
            role="teacher",
            email="john@example.com",
            first_name="John",
            last_name="Smith",
        )
        self.blocked = make_user(
            role="student",
            email="blocked@example.com",
            first_name="Bob",
            last_name="Banned",
            is_blocked=True,
            status=User.StatusChoices.INACTIVE,
        )

    def _result_emails(self, response):
        return [row["email"] for row in response.data["results"]]

    def test_list_returns_paginated_envelope(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_search_matches_first_name(self):
        response = self.client.get(self.url, {"search": "jane"})
        self.assertEqual(self._result_emails(response), ["jane@example.com"])

    def test_search_matches_last_name(self):
        response = self.client.get(self.url, {"search": "smith"})
        self.assertEqual(self._result_emails(response), ["john@example.com"])

    def test_search_matches_email(self):
        response = self.client.get(self.url, {"search": "blocked@"})
        self.assertEqual(self._result_emails(response), ["blocked@example.com"])

    def test_role_filter(self):
        response = self.client.get(self.url, {"role": "student"})
        self.assertEqual(
            sorted(self._result_emails(response)),
            ["blocked@example.com", "jane@example.com"],
        )

    def test_invalid_role_returns_400(self):
        response = self.client.get(self.url, {"role": "wizard"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_filter(self):
        response = self.client.get(self.url, {"status": "inactive"})
        self.assertEqual(self._result_emails(response), ["blocked@example.com"])

    def test_is_blocked_filter(self):
        response = self.client.get(self.url, {"is_blocked": "true"})
        self.assertEqual(self._result_emails(response), ["blocked@example.com"])

    def test_default_ordering_is_newest_first(self):
        response = self.client.get(self.url)
        emails = self._result_emails(response)
        self.assertEqual(emails[0], "blocked@example.com")
        self.assertEqual(emails[-1], "admin_setup@example.com")

    def test_ordering_by_date_joined_ascending(self):
        response = self.client.get(self.url, {"ordering": "date_joined"})
        emails = self._result_emails(response)
        self.assertEqual(emails[0], "admin_setup@example.com")
        self.assertEqual(emails[-1], "blocked@example.com")

    def test_params_combine(self):
        response = self.client.get(
            self.url,
            {"search": "example.com", "role": "student", "ordering": "-date_joined"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._result_emails(response),
            ["blocked@example.com", "jane@example.com"],
        )

    def test_page_size_param_honored(self):
        response = self.client.get(self.url, {"page_size": 2})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 4)

    def test_default_list_includes_deleted(self):
        make_user(email="deleted@example.com", is_deleted=True)
        response = self.client.get(self.url)
        self.assertIn("deleted@example.com", self._result_emails(response))

    def test_is_deleted_filter_shows_only_deleted(self):
        make_user(email="deleted@example.com", is_deleted=True)
        response = self.client.get(self.url, {"is_deleted": "true"})
        self.assertEqual(self._result_emails(response), ["deleted@example.com"])
