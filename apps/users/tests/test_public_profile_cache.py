from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from redis.exceptions import RedisError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatParticipant
from apps.chat.services import ChatService
from apps.common.cache import cache_get_or_set
from apps.users.models import TeacherProfile, UserReport
from apps.users.tests._factories import make_user
from apps.users.views.PublicUserProfileView import PublicUserProfileView

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "public-user-profile-cache-tests",
    }
}


@override_settings(
    CACHES=TEST_CACHES,
    CACHE_TTL_JITTER_SECONDS=60,
    PUBLIC_USER_PROFILE_CACHE_TIMEOUT=600,
)
class PublicUserProfileCacheTests(APITestCase):
    def setUp(self):
        self.viewer = make_user(
            role="student",
            email="profile-viewer@example.com",
            first_name="Profile",
            last_name="Viewer",
        )
        self.target = make_user(
            role="teacher",
            email="profile-target@example.com",
            first_name="Cached",
            last_name="Teacher",
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.target,
            bio="Original bio",
        )
        self.chat, _ = ChatService.create_direct_chat(self.viewer, self.target)
        self.url = reverse("user-public-profile", args=[self.target.pk])
        cache.clear()

    def test_active_chat_profile_reuses_cached_response(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch.object(
            PublicUserProfileView,
            "get_object",
            side_effect=AssertionError("profile queryset should not run"),
        ):
            second = self.client.get(self.url)

        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data, first.data)

    def test_profile_cache_timeout_includes_jitter(self):
        self.client.force_authenticate(self.viewer)

        with (
            patch("apps.common.cache.random.randint", return_value=17),
            patch(
                "apps.users.views.PublicUserProfileView.cache_get_or_set",
                wraps=cache_get_or_set,
            ) as get_or_set,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_or_set.call_args.kwargs["timeout"], 617)

    def test_profile_without_active_chat_is_not_cached(self):
        ChatParticipant.objects.filter(
            chat=self.chat,
            user=self.target,
        ).update(left_at=self.chat.updated_at)
        self.client.force_authenticate(self.viewer)

        first = self.client.get(self.url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        with patch.object(
            PublicUserProfileView,
            "get_object",
            side_effect=AssertionError("uncached profile should query again"),
        ):
            with self.assertRaisesRegex(
                AssertionError,
                "uncached profile should query again",
            ):
                self.client.get(self.url)

    def test_cache_is_separated_by_viewer(self):
        second_viewer = make_user(
            role="student",
            email="second-profile-viewer@example.com",
        )
        ChatService.create_direct_chat(second_viewer, self.target)
        UserReport.objects.create(
            reported_user=self.target,
            reporter=self.viewer,
            reason=UserReport.ReasonChoices.SPAM,
            profile_snapshot={},
        )
        cache.clear()

        self.client.force_authenticate(self.viewer)
        reported_response = self.client.get(self.url)

        self.client.force_authenticate(second_viewer)
        unreported_response = self.client.get(self.url)

        self.assertTrue(reported_response.data["has_reported"])
        self.assertFalse(unreported_response.data["has_reported"])

    def test_cache_is_separated_by_viewer_role(self):
        admin_target = make_user(
            role="administrator",
            email="cached-admin@example.com",
        )
        moderator_viewer = make_user(
            role="moderator",
            email="profile-moderator@example.com",
        )
        ChatService.create_direct_chat(moderator_viewer, admin_target)
        url = reverse("user-public-profile", args=[admin_target.pk])
        cache.clear()

        self.client.force_authenticate(moderator_viewer)
        moderator_response = self.client.get(url)
        self.assertEqual(moderator_response.data["email"], "")

        moderator_viewer.role = "student"
        moderator_viewer.save(update_fields=["role"])
        self.client.force_authenticate(moderator_viewer)
        student_response = self.client.get(url)

        self.assertEqual(student_response.data["email"], "")

    def test_user_change_invalidates_cached_profile(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(self.url)
        self.assertEqual(first.data["first_name"], "Cached")

        with self.captureOnCommitCallbacks(execute=True):
            self.target.first_name = "Updated"
            self.target.save(update_fields=["first_name"])

        second = self.client.get(self.url)
        self.assertEqual(second.data["first_name"], "Updated")

    def test_role_profile_change_invalidates_cached_profile(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(self.url)
        self.assertEqual(first.data["profile"]["bio"], "Original bio")

        with self.captureOnCommitCallbacks(execute=True):
            self.teacher_profile.bio = "Updated bio"
            self.teacher_profile.save(update_fields=["bio"])

        second = self.client.get(self.url)
        self.assertEqual(second.data["profile"]["bio"], "Updated bio")

    def test_report_change_invalidates_viewer_state(self):
        self.client.force_authenticate(self.viewer)
        first = self.client.get(self.url)
        self.assertFalse(first.data["has_reported"])

        with self.captureOnCommitCallbacks(execute=True):
            UserReport.objects.create(
                reported_user=self.target,
                reporter=self.viewer,
                reason=UserReport.ReasonChoices.SPAM,
                profile_snapshot={},
            )

        second = self.client.get(self.url)
        self.assertTrue(second.data["has_reported"])

    def test_redis_failure_falls_back_to_database(self):
        self.client.force_authenticate(self.viewer)
        redis_error = RedisError("Redis unavailable")

        with (
            self.assertLogs("apps.common.cache", level="WARNING"),
            patch("apps.common.cache.cache.get", side_effect=redis_error),
            patch("apps.common.cache.cache.add", side_effect=redis_error),
            patch("apps.common.cache.cache.set", side_effect=redis_error),
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.target.pk)
