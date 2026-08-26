from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.tests._factories import make_user


class UserSearchTests(APITestCase):
    def setUp(self):
        self.requester = make_user(email="requester@example.com")
        self.student = make_user(email="student-search@example.com")
        self.teacher = make_user(
            role=User.RoleChoices.TEACHER,
            email="teacher-search@example.com",
        )
        make_user(
            role=User.RoleChoices.MODERATOR,
            email="moderator-search@example.com",
        )
        make_user(
            role=User.RoleChoices.ADMINISTRATOR,
            email="administrator-search@example.com",
        )
        self.client.force_authenticate(user=self.requester)

    def test_search_excludes_moderators_and_administrators(self):
        response = self.client.get(reverse("user-search"), {"email": "search"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {user["id"] for user in response.data},
            {self.student.id, self.teacher.id},
        )

    def test_search_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(reverse("user-search"), {"email": "search"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
