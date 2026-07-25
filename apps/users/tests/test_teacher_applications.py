from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category
from apps.users.models import ModeratorProfile, TeacherApplication, User
from apps.users.services.teacher_application_service import TeacherApplicationService
from apps.users.tokens import teacher_invitation_token

from ._factories import make_user


def _make_moderator(email="moderator@example.com"):
    moderator = make_user(role=User.RoleChoices.MODERATOR, email=email)
    ModeratorProfile.objects.create(user=moderator, level="junior")
    return moderator


def _application_payload(**overrides):
    payload = {
        "first_name": "Олена",
        "last_name": "Коваль",
        "email": "applicant@example.com",
        "date_of_birth": "1990-01-01",
        "phone_number": "+380501234567",
        "bio": "Викладаю англійську 5 років.",
        "experience": "5 років у мовній школі.",
        "specialization": "Англійська мова",
        "years_experience": 5,
        "motivation": "Хочу ділитися знаннями на платформі.",
    }
    payload.update(overrides)
    return payload


class TeacherApplicationSubmitTests(APITestCase):
    def setUp(self):
        self.url = reverse("teacher-application-submit")
        # The endpoint is throttle-scoped ("teacher_application": "5/hour");
        # this class alone issues more than 5 requests across its tests.
        cache.clear()
        self.addCleanup(cache.clear)

    def test_submit_creates_pending_application(self):
        response = self.client.post(self.url, _application_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = TeacherApplication.objects.get(email="applicant@example.com")
        self.assertEqual(application.status, TeacherApplication.StatusChoices.PENDING)

    def test_submit_with_directions(self):
        category = Category.objects.create(name_en="Мови", slug="movy")

        response = self.client.post(
            self.url, _application_payload(directions=[category.id]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        application = TeacherApplication.objects.get(email="applicant@example.com")
        self.assertEqual(list(application.directions.all()), [category])

    def test_submit_rejects_email_of_existing_user(self):
        make_user(role="student", email="taken@example.com")

        response = self.client.post(
            self.url, _application_payload(email="taken@example.com"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_rejects_duplicate_pending_application(self):
        self.client.post(self.url, _application_payload(), format="json")

        response = self.client.post(self.url, _application_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            TeacherApplication.objects.filter(email="applicant@example.com").count(), 1
        )

    def test_submit_allowed_again_after_cancellation(self):
        first = TeacherApplication.objects.create(**_application_payload())
        first.status = TeacherApplication.StatusChoices.CANCELLED
        first.save()

        response = self.client.post(self.url, _application_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TeacherApplicationEmailCheckTests(APITestCase):
    def setUp(self):
        self.url = reverse("teacher-application-check-email")
        cache.clear()
        self.addCleanup(cache.clear)

    def test_available_for_unused_email(self):
        response = self.client.get(self.url, {"email": "free@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["available"])

    def test_unavailable_for_existing_user(self):
        make_user(role="student", email="taken@example.com")

        response = self.client.get(self.url, {"email": "taken@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])
        self.assertTrue(response.data["detail"])

    def test_unavailable_for_pending_application(self):
        TeacherApplication.objects.create(**_application_payload())

        response = self.client.get(self.url, {"email": "applicant@example.com"})

        self.assertFalse(response.data["available"])

    def test_available_again_after_cancellation(self):
        application = TeacherApplication.objects.create(**_application_payload())
        application.status = TeacherApplication.StatusChoices.CANCELLED
        application.save()

        response = self.client.get(self.url, {"email": "applicant@example.com"})

        self.assertTrue(response.data["available"])


class TeacherApplicationModerationPermissionTests(APITestCase):
    def setUp(self):
        self.url = reverse("teacher-applications-list")

    def test_anonymous_forbidden(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_student_forbidden(self):
        student = make_user(role="student", email="student@example.com")
        self.client.force_authenticate(user=student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_allowed(self):
        moderator = _make_moderator()
        self.client.force_authenticate(user=moderator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TeacherApplicationApproveTests(APITestCase):
    def setUp(self):
        self.moderator = _make_moderator()
        self.client.force_authenticate(user=self.moderator)
        self.application = TeacherApplication.objects.create(**_application_payload())

    def _approve_url(self, application=None):
        return reverse("teacher-applications-approve", args=[(application or self.application).pk])

    def test_approve_creates_teacher_user_and_profile(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_teacher_invitation_email"
        ) as send:
            response = self.client.post(self._approve_url(), {"comment": "Виглядає добре"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, TeacherApplication.StatusChoices.APPROVED)
        self.assertEqual(self.application.moderator_profile, self.moderator.moderator_profile)
        self.assertIsNotNone(self.application.created_user)

        user = self.application.created_user
        self.assertEqual(user.role, User.RoleChoices.TEACHER)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.status, User.StatusChoices.INACTIVE)
        self.assertFalse(user.has_usable_password())

        profile = user.teacher_profile
        self.assertEqual(profile.bio, self.application.bio)
        self.assertEqual(profile.experience, self.application.experience)
        self.assertEqual(profile.specialization, self.application.specialization)
        self.assertEqual(profile.years_experience, self.application.years_experience)

        send.assert_called_once_with(user)

    def test_approve_twice_returns_conflict(self):
        with patch("apps.users.services.email_service.EmailService.send_teacher_invitation_email"):
            self.client.post(self._approve_url())

        response = self.client.post(self._approve_url(), {"comment": "again"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class TeacherApplicationCancelTests(APITestCase):
    def setUp(self):
        self.moderator = _make_moderator()
        self.client.force_authenticate(user=self.moderator)
        self.application = TeacherApplication.objects.create(**_application_payload())

    def _cancel_url(self):
        return reverse("teacher-applications-cancel", args=[self.application.pk])

    def test_cancel_sends_email_and_creates_no_user(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_teacher_application_cancelled_email"
        ) as send:
            response = self.client.post(self._cancel_url(), {"comment": "Недостатньо досвіду"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, TeacherApplication.StatusChoices.CANCELLED)
        self.assertEqual(self.application.moderator_comment, "Недостатньо досвіду")
        self.assertIsNone(self.application.created_user)
        self.assertFalse(User.all_objects.filter(email=self.application.email).exists())
        send.assert_called_once_with(self.application)


class TeacherInvitationConfirmTests(APITestCase):
    def setUp(self):
        moderator = _make_moderator()
        application = TeacherApplication.objects.create(**_application_payload())
        with patch("apps.users.services.email_service.EmailService.send_teacher_invitation_email"):
            self.user = TeacherApplicationService.approve(application, moderator.moderator_profile)

    def _uid_and_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = teacher_invitation_token.make_token(self.user)
        return uid, token

    def test_validate_returns_valid_before_completion(self):
        uid, token = self._uid_and_token()

        response = self.client.get(reverse("auth-teacher-invitation-validate", args=[uid, token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_confirm_sets_password_and_activates_account(self):
        uid, token = self._uid_and_token()

        response = self.client.post(
            reverse("auth-teacher-invitation-confirm", args=[uid, token]),
            {"password": "NewStrongPass456"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass456"))
        self.assertTrue(self.user.is_email_verified)
        self.assertEqual(self.user.status, User.StatusChoices.ACTIVE)

    def test_confirm_token_one_use(self):
        uid, token = self._uid_and_token()
        url = reverse("auth-teacher-invitation-confirm", args=[uid, token])

        first = self.client.post(url, {"password": "NewStrongPass456"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(url, {"password": "AnotherPass789"})
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_blocked_until_invitation_confirmed(self):
        response = self.client.post(
            reverse("auth-login"), {"email": self.user.email, "password": "anything"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
