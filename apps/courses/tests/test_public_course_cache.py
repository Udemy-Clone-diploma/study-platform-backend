from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase

from apps.courses.cache import (
    public_course_detail_cache_key,
    public_course_list_cache_key,
    public_featured_categories_cache_key,
    public_new_courses_cache_key,
    public_popular_courses_cache_key,
)
from apps.courses.models import (
    Course,
    CourseDeliveryFormat,
    PricingPlan,
)
from apps.courses.services import CourseService
from apps.courses.views.CourseViewSet import CourseViewSet
from apps.courses.views.CategoryViewSet import CategoryViewSet
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student

from ._factories import make_category, make_course, make_teacher

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "public-course-cache-tests",
    }
}


@override_settings(
    CACHES=TEST_CACHES,
    PUBLIC_COURSE_LIST_CACHE_TIMEOUT=300,
    PUBLIC_COURSE_DETAIL_CACHE_TIMEOUT=600,
    PUBLIC_CATEGORY_CACHE_TIMEOUT=600,
)
class PublicCourseResponseCacheTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.teacher = make_teacher(
            email="cache-teacher@example.com",
            first_name="Cached",
            last_name="Teacher",
        )
        cls.category = make_category(
            name="Cached category",
            slug="cached-category",
            featured_order=1,
            name_uk="Кешована категорія",
            description_en="Cached category description",
            description_uk="Опис кешованої категорії",
        )
        cls.course = make_course(
            cls.teacher,
            title="Cached course",
            slug="cached-course",
            category=cls.category,
            status=Course.StatusChoices.PUBLISHED,
        )

    def setUp(self):
        cache.clear()

    def test_catalog_list_reuses_cached_response(self):
        url = reverse("courses-list")
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)

        with patch.object(
            CourseViewSet,
            "get_queryset",
            side_effect=AssertionError("catalog queryset should not run"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data, first.data)

    def test_public_detail_reuses_cached_response(self):
        url = reverse("courses-public", args=[self.course.slug])
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)

        with patch.object(
            CourseViewSet,
            "get_object",
            side_effect=AssertionError("course lookup should not run"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data, first.data)

    def test_new_and_popular_endpoints_reuse_cached_service_results(self):
        cases = [
            ("new-courses", "get_new_courses"),
            ("popular-courses", "get_popular_courses"),
        ]

        for url_name, service_method in cases:
            with self.subTest(endpoint=url_name):
                cache.clear()
                url = reverse(url_name)
                first = self.client.get(url)
                self.assertEqual(first.status_code, 200)

                with patch.object(
                    CourseService,
                    service_method,
                    side_effect=AssertionError("course service should not run"),
                ):
                    second = self.client.get(url)

                self.assertEqual(second.data, first.data)

    def test_public_category_list_reuses_cached_response(self):
        url = reverse("categories-list")
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)

        with patch.object(
            CategoryViewSet,
            "get_queryset",
            side_effect=AssertionError("category queryset should not run"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.data, first.data)

    def test_featured_categories_reuse_cached_service_result(self):
        url = reverse("categories-featured")
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)

        with patch.object(
            CourseService,
            "get_categories",
            side_effect=AssertionError("category service should not run"),
        ):
            second = self.client.get(url)

        self.assertEqual(second.data, first.data)

    def test_query_parameter_order_produces_same_catalog_key(self):
        factory = APIRequestFactory()
        first = Request(factory.get("/api/v1/courses/?search=python&page=2"))
        second = Request(factory.get("/api/v1/courses/?page=2&search=python"))
        different = Request(factory.get("/api/v1/courses/?page=3&search=python"))

        self.assertEqual(
            public_course_list_cache_key(first),
            public_course_list_cache_key(second),
        )
        self.assertNotEqual(
            public_course_list_cache_key(first),
            public_course_list_cache_key(different),
        )

    def test_localized_public_endpoints_use_distinct_cache_keys(self):
        factory = APIRequestFactory()
        english = Request(factory.get("/api/v1/courses/cached-course/public/?lang=en"))
        ukrainian = Request(factory.get("/api/v1/courses/cached-course/public/?lang=uk"))

        key_builders = (
            lambda request: public_course_detail_cache_key(
                request,
                self.course.slug,
            ),
            lambda request: public_new_courses_cache_key(request, 8),
            lambda request: public_popular_courses_cache_key(request, 8),
            lambda request: public_featured_categories_cache_key(request, 6),
        )
        for build_key in key_builders:
            with self.subTest(key_builder=build_key):
                self.assertNotEqual(build_key(english), build_key(ukrainian))

    def test_featured_categories_cache_preserves_requested_locale(self):
        url = reverse("categories-featured")

        english = self.client.get(url, {"lang": "en"})
        ukrainian = self.client.get(url, {"lang": "uk"})

        self.assertEqual(english.status_code, 200)
        self.assertEqual(ukrainian.status_code, 200)
        self.assertEqual(english.data[0]["name"], "Cached category")
        self.assertEqual(ukrainian.data[0]["name"], "Кешована категорія")

    def test_course_save_invalidates_catalog_and_detail(self):
        list_url = reverse("courses-list")
        detail_url = reverse("courses-public", args=[self.course.slug])
        self.client.get(list_url)
        self.client.get(detail_url)

        with self.captureOnCommitCallbacks(execute=True):
            self.course.title = "Updated cached course"
            self.course.save(update_fields=["title"])

        list_response = self.client.get(list_url)
        detail_response = self.client.get(detail_url)

        self.assertEqual(
            list_response.data["results"][0]["title"],
            "Updated cached course",
        )
        self.assertEqual(detail_response.data["title"], "Updated cached course")

    def test_curriculum_change_invalidates_public_detail(self):
        url = reverse("courses-public", args=[self.course.slug])
        first = self.client.get(url)
        self.assertEqual(first.data["modules"], [])

        with self.captureOnCommitCallbacks(execute=True):
            module = Module.objects.create(
                course=self.course,
                title="New public module",
                order=1,
            )
            Lesson.objects.create(
                module=module,
                title="New lesson",
                order=1,
            )

        second = self.client.get(url)

        self.assertEqual(second.data["modules"][0]["title"], "New public module")
        self.assertEqual(
            second.data["modules"][0]["lessons"][0]["title"],
            "New lesson",
        )

    def test_pricing_change_invalidates_public_catalog(self):
        url = reverse("courses-list")
        first = self.client.get(url)
        self.assertIsNone(first.data["results"][0]["price"])

        with self.captureOnCommitCallbacks(execute=True):
            delivery_format = CourseDeliveryFormat.objects.create(
                course=self.course,
                format_type=CourseDeliveryFormat.FormatType.SELF_PACED,
            )
            PricingPlan.objects.create(
                delivery_format=delivery_format,
                price="49.00",
                currency=PricingPlan.CurrencyChoices.USD,
            )

        second = self.client.get(url)

        self.assertEqual(second.data["results"][0]["price"], "49.00")

    def test_enrollment_change_invalidates_public_counts(self):
        url = reverse("courses-list")
        first = self.client.get(url)
        self.assertEqual(first.data["results"][0]["students_count"], 0)

        _, student_profile = make_student(email="cache-student@example.com")
        with self.captureOnCommitCallbacks(execute=True):
            Enrollment.objects.create(
                student_profile=student_profile,
                course=self.course,
            )

        second = self.client.get(url)

        self.assertEqual(second.data["results"][0]["students_count"], 1)

    def test_lesson_open_state_does_not_invalidate_public_catalog(self):
        _, student_profile = make_student(email="cache-opened-student@example.com")
        enrollment = Enrollment.objects.create(
            student_profile=student_profile,
            course=self.course,
        )
        cache.clear()
        request = Request(APIRequestFactory().get("/api/v1/courses/"))
        before = public_course_list_cache_key(request)

        enrollment.last_opened_at = timezone.now()
        enrollment.save(update_fields=["last_opened_at"])

        after = public_course_list_cache_key(request)
        self.assertEqual(after, before)

    def test_teacher_change_invalidates_public_detail(self):
        url = reverse("courses-public", args=[self.course.slug])
        first = self.client.get(url)
        self.assertEqual(first.data["teacher"]["name"], "Cached Teacher")

        with self.captureOnCommitCallbacks(execute=True):
            teacher_user = self.teacher.user
            teacher_user.first_name = "Updated"
            teacher_user.save(update_fields=["first_name"])

        second = self.client.get(url)

        self.assertEqual(second.data["teacher"]["name"], "Updated Teacher")

    def test_public_category_count_excludes_draft_courses(self):
        make_course(
            self.teacher,
            title="Draft in category",
            slug="draft-in-category",
            category=self.category,
            status=Course.StatusChoices.DRAFT,
        )

        response = self.client.get(reverse("categories-list"))
        category = next(
            item
            for item in response.data["results"]
            if item["id"] == self.category.id
        )

        self.assertEqual(category["courses_count"], 1)
