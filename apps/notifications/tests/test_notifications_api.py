from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import Notification

from ._factories import make_notification, make_user


class NotificationListTests(APITestCase):
    def setUp(self):
        self.user = make_user("list_owner@example.com")
        self.other = make_user("list_other@example.com")
        self.url = reverse("notifications-list")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_only_own_notifications(self):
        make_notification(self.user, title="Mine")
        make_notification(self.other, title="Theirs")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Mine")

    def test_ordered_newest_first(self):
        first = make_notification(self.user, title="First")
        second = make_notification(self.user, title="Second")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [second.id, first.id])

    def test_filter_by_is_read(self):
        make_notification(self.user, title="Unread", is_read=False)
        make_notification(self.user, title="Read", is_read=True)

        self.client.force_authenticate(user=self.user)

        unread = self.client.get(self.url, {"is_read": "false"})
        self.assertEqual(unread.data["count"], 1)
        self.assertEqual(unread.data["results"][0]["title"], "Unread")

        read = self.client.get(self.url, {"is_read": "true"})
        self.assertEqual(read.data["count"], 1)
        self.assertEqual(read.data["results"][0]["title"], "Read")

    def test_actor_is_serialized(self):
        actor = make_user(
            "list_actor@example.com",
            role="teacher",
            first_name="Ada",
            last_name="Lovelace",
        )
        make_notification(self.user, actor=actor)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        actor_data = response.data["results"][0]["actor"]
        self.assertEqual(actor_data["id"], actor.id)
        self.assertEqual(actor_data["name"], "Ada Lovelace")
        self.assertIsNone(actor_data["avatar"])


class NotificationUpdateDeleteTests(APITestCase):
    def setUp(self):
        self.user = make_user("upd_owner@example.com")
        self.other = make_user("upd_other@example.com")

    def test_patch_marks_as_read(self):
        notification = make_notification(self.user, is_read=False)

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            reverse("notifications-detail", args=[notification.id]),
            {"is_read": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_patch_cannot_change_read_only_fields(self):
        notification = make_notification(self.user, title="Original")

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            reverse("notifications-detail", args=[notification.id]),
            {"title": "Hacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.title, "Original")

    def test_cannot_patch_another_users_notification(self):
        notification = make_notification(self.other)

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            reverse("notifications-detail", args=[notification.id]),
            {"is_read": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_notification(self):
        notification = make_notification(self.user)

        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse("notifications-detail", args=[notification.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=notification.id).exists())

    def test_cannot_delete_another_users_notification(self):
        notification = make_notification(self.other)

        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse("notifications-detail", args=[notification.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(id=notification.id).exists())


class NotificationUnreadCountTests(APITestCase):
    def setUp(self):
        self.user = make_user("count_owner@example.com")
        self.other = make_user("count_other@example.com")
        self.url = reverse("notifications-unread-count")

    def test_counts_only_own_unread(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        make_notification(self.other, is_read=False)

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationMarkAllReadTests(APITestCase):
    def setUp(self):
        self.user = make_user("markall_owner@example.com")
        self.other = make_user("markall_other@example.com")
        self.url = reverse("notifications-mark-all-read")

    def test_marks_all_own_unread_and_reports_count(self):
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=False)
        make_notification(self.user, is_read=True)
        other_unread = make_notification(self.other, is_read=False)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)
        other_unread.refresh_from_db()
        self.assertFalse(other_unread.is_read)

    def test_requires_authentication(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
