from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import NotificationPreference
from apps.notifications.preferences import DEFAULT_NOTIFICATION_PREFERENCES

from ._factories import make_user


class NotificationPreferenceReadTests(APITestCase):
    def setUp(self):
        self.user = make_user("pref_read@example.com")
        self.url = reverse("notification-preferences")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_defaults_when_no_overrides(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, DEFAULT_NOTIFICATION_PREFERENCES)

    def test_overrides_applied_on_top_of_defaults(self):
        NotificationPreference.objects.create(
            user=self.user, overrides={"new_message": {"email": True}}
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        # new_message email flipped on; in_app keeps its default.
        self.assertEqual(response.data["new_message"], {"in_app": True, "email": True})
        # Untouched types keep defaults.
        self.assertEqual(
            response.data["homework_graded"],
            DEFAULT_NOTIFICATION_PREFERENCES["homework_graded"],
        )


class NotificationPreferenceUpdateTests(APITestCase):
    def setUp(self):
        self.user = make_user("pref_update@example.com")
        self.url = reverse("notification-preferences")
        self.client.force_authenticate(user=self.user)

    def test_patch_persists_override_and_returns_effective(self):
        response = self.client.patch(self.url, {"new_message": {"email": True}}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["new_message"], {"in_app": True, "email": True})

        pref = NotificationPreference.objects.get(user=self.user)
        self.assertEqual(pref.overrides, {"new_message": {"email": True}})

    def test_patch_merges_with_existing_overrides(self):
        NotificationPreference.objects.create(
            user=self.user, overrides={"new_message": {"email": True}}
        )

        response = self.client.patch(self.url, {"new_message": {"in_app": False}}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pref = NotificationPreference.objects.get(user=self.user)
        self.assertEqual(pref.overrides, {"new_message": {"email": True, "in_app": False}})

    def test_unknown_type_rejected(self):
        response = self.client.patch(self.url, {"not_a_type": {"email": True}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())

    def test_unknown_channel_rejected(self):
        response = self.client.patch(self.url, {"new_message": {"sms": True}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_boolean_value_rejected(self):
        response = self.client.patch(self.url, {"new_message": {"email": "yes"}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_object_body_rejected(self):
        response = self.client.patch(self.url, ["new_message"], format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
