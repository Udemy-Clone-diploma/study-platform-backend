from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course, Tag
from apps.users.models import ModeratorProfile, User

from ._factories import make_category, make_course, make_teacher


class CourseViewSetTests(APITestCase):
    def setUp(self):
        teacher_user, self.teacher_profile = make_teacher()
        moderator_user = User.objects.create_user(
            email="moderator@example.com",
            password="pass12345",
            role="moderator",
        )
        self.moderator_profile = ModeratorProfile.objects.create(
            user=moderator_user,
            level="senior",
        )
        self.client.force_authenticate(user=teacher_user)
        self.category = make_category(description="Programming courses")
        self.tag = Tag.objects.create(name="Python")
        self.course = make_course(
            self.teacher_profile,
            title="Backend Engineering",
            slug="backend-engineering",
            short_description="Learn APIs",
            full_description="A deep dive into backend development.",
            moderator_profile=self.moderator_profile,
            category=self.category,
            duration_hours=12,
            lessons_count=6,
            status=Course.StatusChoices.DRAFT,
        )
        self.course.tags.add(self.tag)

    def test_list_uses_list_serializer(self):
        self.course.status = Course.StatusChoices.PUBLISHED
        self.course.save(update_fields=["status"])

        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["slug"], self.course.slug)
        self.assertNotIn("full_description", results[0])
        self.assertEqual(results[0]["teacher_name"], "")

    def test_retrieve_uses_detail_serializer(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_description"], self.course.full_description)
        self.assertEqual(response.data["teacher"]["id"], self.teacher_profile.pk)
        self.assertEqual(response.data["moderator_id"], self.moderator_profile.pk)

    def test_create_course(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Advanced Django",
                "short_description": "Build production APIs",
                "full_description": "Advanced patterns for Django and DRF.",
                "teacher_profile": self.teacher_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.DRAFT,
                "tag_ids": [self.tag.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["full_description"],
            "Advanced patterns for Django and DRF.",
        )
        self.assertEqual(response.data["slug"], "advanced-django")
        self.assertEqual(response.data["category"]["id"], self.category.pk)
        self.assertEqual(response.data["tags"][0]["id"], self.tag.pk)

    def test_create_course_ignores_provided_slug(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Advanced Django",
                "short_description": "Build production APIs",
                "full_description": "Advanced patterns for Django and DRF.",
                "slug": "teacher-custom-slug",
                "teacher_profile": self.teacher_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "advanced-django")

    def test_create_course_generates_unique_slug_when_title_repeats(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": self.course.title,
                "short_description": "Another course with the same title",
                "full_description": "Same title, different course.",
                "teacher_profile": self.teacher_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "duration_hours": 8,
                "lessons_count": 4,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "backend-engineering-2")

    def test_partial_update_course(self):
        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {
                "title": "Backend Engineering Pro",
                "tag_ids": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Backend Engineering Pro")
        self.assertEqual(response.data["slug"], "backend-engineering-pro")
        self.assertEqual(response.data["tags"], [])

    def test_partial_update_does_not_allow_slug_override(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {
                "title": "Backend Engineering Updated",
                "slug": "teacher-edited-slug",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering")

    def test_partial_update_regenerates_slug_for_draft_when_title_changes(self):
        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Backend Engineering Intensive"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering-intensive")

    def test_partial_update_keeps_slug_for_non_draft_when_title_changes(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Backend Engineering Intensive"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering")

    def test_soft_delete_course(self):
        response = self.client.delete(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_deleted)
        self.assertEqual(self.course.status, Course.StatusChoices.ARCHIVED)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())


