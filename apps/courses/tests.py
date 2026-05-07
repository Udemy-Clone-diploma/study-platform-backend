from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category, Course, Tag
from apps.users.models import ModeratorProfile, TeacherProfile, User


class CourseViewSetTests(APITestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(
            email="teacher@example.com",
            password="pass12345",
            role="teacher",
        )
        moderator_user = User.objects.create_user(
            email="moderator@example.com",
            password="pass12345",
            role="moderator",
        )

        self.teacher_profile = TeacherProfile.objects.create(user=teacher_user)
        self.moderator_profile = ModeratorProfile.objects.create(
            user=moderator_user,
            level="senior",
        )
        self.client.force_authenticate(user=teacher_user)
        self.category = Category.objects.create(
            name="Development",
            slug="development",
            description="Programming courses",
        )
        self.tag = Tag.objects.create(name="Python")
        self.course = Course.all_objects.create(
            title="Backend Engineering",
            short_description="Learn APIs",
            full_description="A deep dive into backend development.",
            slug="backend-engineering",
            teacher_profile=self.teacher_profile,
            moderator_profile=self.moderator_profile,
            category=self.category,
            level=Course.LevelChoices.BEGINNER,
            language=Course.LanguageChoices.ENGLISH,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            pricing_type=Course.PricingTypeChoices.FREE,
            price=0,
            duration_hours=12,
            lessons_count=6,
            status=Course.StatusChoices.DRAFT,
        )
        self.course.tags.add(self.tag)

    def test_list_uses_list_serializer(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["slug"], self.course.slug)
        self.assertNotIn("full_description", results[0])
        self.assertEqual(results[0]["teacher_name"], "")

    def test_retrieve_uses_detail_serializer(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_description"], self.course.full_description)
        self.assertEqual(response.data["teacher_id"], self.teacher_profile.pk)
        self.assertEqual(response.data["moderator_id"], self.moderator_profile.pk)

    def test_create_course(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Advanced Django",
                "short_description": "Build production APIs",
                "full_description": "Advanced patterns for Django and DRF.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "199.99",
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.REVIEW,
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
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "199.99",
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.REVIEW,
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
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
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
            reverse("courses-detail", args=[self.course.pk]),
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

    def test_create_free_course_normalizes_price_and_installments(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Free Django Basics",
                "short_description": "Learn the basics",
                "full_description": "Introductory course content.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
                "price": "149.99",
                "installment_count": 6,
                "installment_amount": "24.99",
                "duration_hours": 8,
                "lessons_count": 4,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["price"], "0.00")
        self.assertIsNone(response.data["installment_count"])
        self.assertIsNone(response.data["installment_amount"])

    def test_partial_update_full_payment_clears_installment_fields(self):
        installment_course = Course.all_objects.create(
            title="Installment Course",
            short_description="Pay in parts",
            full_description="Installment pricing example.",
            slug="installment-course",
            teacher_profile=self.teacher_profile,
            moderator_profile=self.moderator_profile,
            category=self.category,
            level=Course.LevelChoices.INTERMEDIATE,
            language=Course.LanguageChoices.ENGLISH,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.GROUP,
            course_type=Course.CourseTypeChoices.PROFESSION,
            pricing_type=Course.PricingTypeChoices.INSTALLMENT,
            price="300.00",
            installment_count=3,
            installment_amount="100.00",
            duration_hours=18,
            lessons_count=9,
            status=Course.StatusChoices.REVIEW,
        )

        response = self.client.patch(
            reverse("courses-detail", args=[installment_course.pk]),
            {
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "300.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["installment_count"])
        self.assertIsNone(response.data["installment_amount"])

        installment_course.refresh_from_db()
        self.assertIsNone(installment_course.installment_count)
        self.assertIsNone(installment_course.installment_amount)

    def test_installment_pricing_requires_installment_fields(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Broken Installments",
                "short_description": "Missing installment data",
                "full_description": "This should fail.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.INDIVIDUAL,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.INSTALLMENT,
                "price": "120.00",
                "duration_hours": 10,
                "lessons_count": 5,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("installment_count", response.data)
        self.assertIn("installment_amount", response.data)

    def test_partial_update_does_not_allow_slug_override(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.pk]),
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
            reverse("courses-detail", args=[self.course.pk]),
            {
                "title": "Backend Engineering Intensive",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering-intensive")

    def test_partial_update_keeps_slug_for_non_draft_when_title_changes(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.pk]),
            {
                "title": "Backend Engineering Intensive",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering")

    def test_soft_delete_course(self):
        response = self.client.delete(reverse("courses-detail", args=[self.course.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_deleted)
        self.assertEqual(self.course.status, Course.StatusChoices.ARCHIVED)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())


class CategoryViewSetTests(APITestCase):
    def setUp(self):
        self.category_dev = Category.objects.create(
            name="Development",
            slug="development",
            description="Programming courses",
        )
        self.category_design = Category.objects.create(
            name="Design",
            slug="design",
            description="Design courses",
        )

    def test_list_returns_all_categories(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_returns_correct_fields(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        category = response.data["results"][0]
        self.assertIn("id", category)
        self.assertIn("name", category)
        self.assertIn("slug", category)
        self.assertIn("description", category)


class CourseFilterTests(APITestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(
            email="teacher@example.com",
            password="pass12345",
            role="teacher",
        )
        self.teacher_profile = TeacherProfile.objects.create(user=teacher_user)

        self.category_dev = Category.objects.create(
            name="Development",
            slug="development",
        )
        self.category_design = Category.objects.create(
            name="Design",
            slug="design",
        )

        base = dict(
            short_description="Short",
            full_description="Full",
            teacher_profile=self.teacher_profile,
            level=Course.LevelChoices.BEGINNER,
            language=Course.LanguageChoices.ENGLISH,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            pricing_type=Course.PricingTypeChoices.FREE,
            price=0,
            duration_hours=10,
        )
        self.course_dev = Course.all_objects.create(
            title="Django Course",
            slug="django-course",
            category=self.category_dev,
            **base,
        )
        self.course_design = Course.all_objects.create(
            title="Figma Course",
            slug="figma-course",
            category=self.category_design,
            **base,
        )
        self.course_no_category = Course.all_objects.create(
            title="No Category Course",
            slug="no-category-course",
            category=None,
            **base,
        )

    def test_filter_by_category_slug_returns_matching_courses(self):
        response = self.client.get(
            reverse("courses-list"), {"category": "development"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "django-course")

    def test_filter_by_category_slug_excludes_other_categories(self):
        response = self.client.get(
            reverse("courses-list"), {"category": "design"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertIn("figma-course", slugs)
        self.assertNotIn("django-course", slugs)

    def test_filter_by_nonexistent_slug_returns_empty_list(self):
        response = self.client.get(
            reverse("courses-list"), {"category": "nonexistent-category"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_search_returns_courses_matching_title(self):
        response = self.client.get(reverse("courses-list"), {"search": "django"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["django-course"])

    def test_search_returns_courses_matching_category(self):
        response = self.client.get(reverse("courses-list"), {"search": "design"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertIn("figma-course", slugs)
        self.assertNotIn("django-course", slugs)

    def test_search_can_be_combined_with_category_filter(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "development", "search": "figma"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_no_filter_returns_all_courses(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)


class CoursePaginationTests(APITestCase):
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    @classmethod
    def setUpTestData(cls):
        teacher_user = User.objects.create_user(
            email="teacher@example.com",
            password="pass12345",
            role="teacher",
        )
        cls.teacher_profile = TeacherProfile.objects.create(user=teacher_user)
        cls.category = Category.objects.create(name="Development", slug="development")
        cls.other_category = Category.objects.create(name="Design", slug="design")

        base = dict(
            short_description="Short",
            full_description="Full",
            teacher_profile=cls.teacher_profile,
            level=Course.LevelChoices.BEGINNER,
            language=Course.LanguageChoices.ENGLISH,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            pricing_type=Course.PricingTypeChoices.FREE,
            price=0,
            duration_hours=10,
        )
        # 25 dev courses with varied prices to enable ordering checks
        for i in range(25):
            Course.all_objects.create(
                title=f"Dev Course {i:02d}",
                slug=f"dev-course-{i:02d}",
                category=cls.category,
                **{**base, "price": i},
            )
        # 3 design courses to verify pagination composes with filters
        for i in range(3):
            Course.all_objects.create(
                title=f"Design Course {i}",
                slug=f"design-course-{i}",
                category=cls.other_category,
                **base,
            )

    def test_default_response_has_pagination_envelope(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)
        self.assertEqual(response.data["count"], 28)
        self.assertEqual(len(response.data["results"]), self.DEFAULT_PAGE_SIZE)
        self.assertIsNone(response.data["previous"])
        self.assertIsNotNone(response.data["next"])

    def test_page_param_returns_next_page(self):
        response = self.client.get(reverse("courses-list"), {"page": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 28 total, page_size 20 → page 2 has 8 items
        self.assertEqual(len(response.data["results"]), 8)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_page_size_query_param_overrides_default(self):
        response = self.client.get(reverse("courses-list"), {"page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["count"], 28)

    def test_page_size_capped_at_max(self):
        response = self.client.get(
            reverse("courses-list"), {"page_size": self.MAX_PAGE_SIZE + 50}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # only 28 courses exist, but cap means even with a huge request
        # the page can not exceed MAX_PAGE_SIZE
        self.assertLessEqual(len(response.data["results"]), self.MAX_PAGE_SIZE)
        self.assertEqual(len(response.data["results"]), 28)

    def test_invalid_page_returns_404(self):
        response = self.client.get(reverse("courses-list"), {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination_composes_with_filter(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "design", "page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        for course in response.data["results"]:
            self.assertTrue(course["slug"].startswith("design-course-"))

    def test_pagination_composes_with_ordering(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "development", "ordering": "price", "page_size": 5},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [c["price"] for c in response.data["results"]]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(len(prices), 5)

    def test_results_do_not_overlap_between_pages(self):
        first = self.client.get(reverse("courses-list"), {"page": 1, "page_size": 10})
        second = self.client.get(reverse("courses-list"), {"page": 2, "page_size": 10})

        first_ids = {c["id"] for c in first.data["results"]}
        second_ids = {c["id"] for c in second.data["results"]}
        self.assertEqual(first_ids & second_ids, set())


class CategoryPaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(25):
            Category.objects.create(name=f"Category {i:02d}", slug=f"cat-{i:02d}")

    def test_categories_list_is_paginated(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)

    def test_categories_list_respects_page_size(self):
        response = self.client.get(reverse("categories-list"), {"page_size": 7})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 7)


class TopNEndpointsAreNotPaginatedTests(APITestCase):
    """The home-page top-N endpoints return a raw list, not the paginated envelope."""

    @classmethod
    def setUpTestData(cls):
        teacher_user = User.objects.create_user(
            email="teacher@example.com",
            password="pass12345",
            role="teacher",
        )
        cls.teacher_profile = TeacherProfile.objects.create(user=teacher_user)
        Category.objects.create(name="A", slug="a")

    def test_new_courses_endpoint_returns_list(self):
        response = self.client.get(reverse("new-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_popular_courses_endpoint_returns_list(self):
        response = self.client.get(reverse("popular-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_featured_categories_endpoint_returns_list(self):
        response = self.client.get(reverse("categories-featured"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class TopNLimitParamTests(APITestCase):
    """The top-N endpoints accept ?limit=N (capped at MAX_TOP_N_LIMIT)."""

    DEFAULT_NEW = 8
    DEFAULT_POPULAR = 8
    DEFAULT_FEATURED = 6
    MAX_LIMIT = 50

    @classmethod
    def setUpTestData(cls):
        teacher_user = User.objects.create_user(
            email="teacher@example.com",
            password="pass12345",
            role="teacher",
        )
        cls.teacher_profile = TeacherProfile.objects.create(user=teacher_user)

        base = dict(
            short_description="Short",
            full_description="Full",
            teacher_profile=cls.teacher_profile,
            level=Course.LevelChoices.BEGINNER,
            language=Course.LanguageChoices.ENGLISH,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            pricing_type=Course.PricingTypeChoices.FREE,
            price=0,
            duration_hours=10,
            status=Course.StatusChoices.PUBLISHED,
        )
        # 60 published courses to verify capping behavior
        for i in range(60):
            Course.all_objects.create(
                title=f"Top-N Course {i:02d}",
                slug=f"top-n-course-{i:02d}",
                **base,
            )
        for i in range(15):
            Category.objects.create(name=f"Cat {i:02d}", slug=f"cat-{i:02d}")

    def test_new_courses_default_limit(self):
        response = self.client.get(reverse("new-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.DEFAULT_NEW)

    def test_new_courses_explicit_limit(self):
        response = self.client.get(reverse("new-courses"), {"limit": 3})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_new_courses_limit_capped_at_max(self):
        response = self.client.get(reverse("new-courses"), {"limit": 999})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.MAX_LIMIT)

    def test_popular_courses_explicit_limit(self):
        response = self.client.get(reverse("popular-courses"), {"limit": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

    def test_featured_categories_default_limit(self):
        response = self.client.get(reverse("categories-featured"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.DEFAULT_FEATURED)

    def test_featured_categories_explicit_limit(self):
        response = self.client.get(reverse("categories-featured"), {"limit": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

    def test_invalid_limit_returns_400(self):
        for bad_value in ("abc", "0", "-3", "1.5"):
            with self.subTest(value=bad_value):
                response = self.client.get(
                    reverse("new-courses"), {"limit": bad_value}
                )
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn("limit", response.data)


class FeaturedCategoriesUrlTests(APITestCase):
    """The home-page categories endpoint moved from /courses/categories/ to /categories/featured/."""

    def test_old_url_no_longer_returns_featured_list(self):
        # /api/v1/courses/categories/ used to return the top-6 list. It now
        # either 404s or routes to the paginated CategoryViewSet detail (which
        # would 404 because "categories" is not a valid pk).
        response = self.client.get("/api/v1/courses/categories/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_url_works(self):
        response = self.client.get(reverse("categories-featured"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
