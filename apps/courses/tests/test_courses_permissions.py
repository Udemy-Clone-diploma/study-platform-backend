from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.users.models import User

from ._factories import make_category, make_course, make_teacher


class CourseCreatePermissionTests(APITestCase):
    """Only teachers and administrators may POST a new course."""

    def setUp(self):
        self.category = make_category()
        _, self.teacher_profile = make_teacher()

    def _payload(self, **overrides):
        data = {
            "title": "New Course",
            "short_description": "x",
            "full_description": "y",
            "category_id": self.category.pk,
            "level": Course.LevelChoices.BEGINNER,
            "language": Course.LanguageChoices.ENGLISH,
            "mode": Course.ModeChoices.SELF_LEARNING,
            "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
            "course_type": Course.CourseTypeChoices.KNOWLEDGE,
            "pricing_type": Course.PricingTypeChoices.FREE,
            "duration_hours": 5,
            "lessons_count": 0,
            "status": Course.StatusChoices.DRAFT,
        }
        data.update(overrides)
        return data

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            reverse("courses-list"), self._payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_create(self):
        student = User.objects.create_user(
            email="student@example.com", password="pass12345", role="student"
        )
        self.client.force_authenticate(user=student)

        response = self.client.post(
            reverse("courses-list"), self._payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_cannot_create(self):
        moderator = User.objects.create_user(
            email="moderator@example.com", password="pass12345", role="moderator"
        )
        self.client.force_authenticate(user=moderator)

        response = self.client.post(
            reverse("courses-list"), self._payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_can_create(self):
        self.client.force_authenticate(user=self.teacher_profile.user)

        response = self.client.post(
            reverse("courses-list"),
            self._payload(teacher_profile=self.teacher_profile.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_administrator_can_create(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            reverse("courses-list"),
            self._payload(teacher_profile=self.teacher_profile.pk),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CourseUpdateDeletePermissionTests(APITestCase):
    """Only the course's teacher or an administrator may PATCH/DELETE."""

    def setUp(self):
        self.category = make_category()
        _, self.owner_profile = make_teacher(email="owner@example.com")
        _, self.other_teacher_profile = make_teacher(email="other@example.com")
        self.course = make_course(
            self.owner_profile,
            title="Owned Course",
            slug="owned-course",
            category=self.category,
        )

    def test_anonymous_cannot_update(self):
        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "New Title"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_teacher_cannot_update(self):
        self.client.force_authenticate(user=self.other_teacher_profile.user)

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Hijacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_cannot_update(self):
        moderator = User.objects.create_user(
            email="moderator@example.com", password="pass12345", role="moderator"
        )
        self.client.force_authenticate(user=moderator)

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Mod Edit"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update(self):
        self.client.force_authenticate(user=self.owner_profile.user)

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Owner Edit"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_administrator_can_update_any_course(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Admin Edit"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_teacher_cannot_delete(self):
        self.client.force_authenticate(user=self.other_teacher_profile.user)

        response = self.client.delete(
            reverse("courses-detail", args=[self.course.slug])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        self.client.force_authenticate(user=self.owner_profile.user)

        response = self.client.delete(
            reverse("courses-detail", args=[self.course.slug])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TeacherProfilePinningTests(APITestCase):
    """A non-admin teacher cannot spoof teacher_profile to attribute work to others."""

    def setUp(self):
        self.category = make_category()
        _, self.caller_profile = make_teacher(email="caller@example.com")
        _, self.other_profile = make_teacher(email="victim@example.com")

    def test_create_pins_teacher_profile_to_caller(self):
        self.client.force_authenticate(user=self.caller_profile.user)

        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Spoof Attempt",
                "short_description": "x",
                "full_description": "y",
                "category_id": self.category.pk,
                "teacher_profile": self.other_profile.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
                "duration_hours": 5,
                "lessons_count": 0,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["teacher"]["id"], self.caller_profile.pk)

    def test_partial_update_drops_teacher_profile_for_non_admin(self):
        course = make_course(
            self.caller_profile,
            title="Mine",
            slug="mine",
            category=self.category,
        )
        self.client.force_authenticate(user=self.caller_profile.user)

        response = self.client.patch(
            reverse("courses-detail", args=[course.slug]),
            {"teacher_profile": self.other_profile.pk, "title": "Mine Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course.refresh_from_db()
        self.assertEqual(course.teacher_profile_id, self.caller_profile.pk)

    def test_admin_can_assign_teacher_profile(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Admin Assigned",
                "short_description": "x",
                "full_description": "y",
                "category_id": self.category.pk,
                "teacher_profile": self.other_profile.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
                "duration_hours": 5,
                "lessons_count": 0,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["teacher"]["id"], self.other_profile.pk)
