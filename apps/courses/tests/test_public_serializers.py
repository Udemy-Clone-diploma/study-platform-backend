from django.test import SimpleTestCase
from rest_framework import serializers

from apps.courses.serializers import (
    PublicCategorySerializer,
    PublicCourseCohortSerializer,
    PublicCourseDeliveryFormatSerializer,
    PublicCourseDetailSerializer,
    PublicCourseListSerializer,
    PublicCourseTeacherSerializer,
    PublicPricingPlanSerializer,
    PublicTagSerializer,
)
from apps.curriculum.serializers import PublicCourseModuleSerializer


class PublicCourseSerializerContractTests(SimpleTestCase):
    def test_public_course_list_has_only_catalog_fields(self):
        serializer = PublicCourseListSerializer()

        self.assertEqual(
            list(serializer.fields),
            [
                "id",
                "image",
                "title",
                "subtitle",
                "short_description",
                "slug",
                "teacher_name",
                "category",
                "level",
                "language",
                "mode",
                "delivery_type",
                "course_type",
                "price",
                "currency",
                "duration_hours",
                "lessons_count",
                "with_certificate",
                "is_on_sale",
                "rating_avg",
                "rating_count",
                "students_count",
                "students_enrolled_last_30_days",
                "published_at",
                "created_at",
                "tags",
            ],
        )
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))

    def test_public_course_detail_excludes_private_and_personal_fields(self):
        serializer = PublicCourseDetailSerializer()

        self.assertTrue(
            {
                "image_hash",
                "moderator_id",
                "status",
                "moderator_comment",
                "is_enrolled",
                "group_chat_url",
                "moderation_review",
            }.isdisjoint(serializer.fields)
        )
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))

    def test_public_course_detail_uses_public_nested_serializers(self):
        serializer = PublicCourseDetailSerializer()

        self.assertIsInstance(
            serializer.fields["modules"].child,
            PublicCourseModuleSerializer,
        )
        self.assertIsInstance(
            serializer.fields["delivery_formats"].child,
            PublicCourseDeliveryFormatSerializer,
        )
        self.assertIsInstance(
            serializer.fields["cohorts"].child,
            PublicCourseCohortSerializer,
        )
        self.assertIsInstance(
            serializer.fields["teacher"],
            PublicCourseTeacherSerializer,
        )
        self.assertIsInstance(
            serializer.fields["category"],
            PublicCategorySerializer,
        )
        self.assertIsInstance(
            serializer.fields["tags"],
            serializers.ListSerializer,
        )
        self.assertIsInstance(
            serializer.fields["tags"].child,
            PublicTagSerializer,
        )

    def test_public_delivery_format_excludes_chat_and_completion_data(self):
        serializer = PublicCourseDeliveryFormatSerializer()

        self.assertTrue({"chat_id", "completed_count"}.isdisjoint(serializer.fields))
        self.assertIsInstance(
            serializer.fields["pricing"],
            PublicPricingPlanSerializer,
        )

    def test_public_cohort_excludes_chat_and_members(self):
        serializer = PublicCourseCohortSerializer()

        self.assertTrue({"chat_id", "members"}.isdisjoint(serializer.fields))

    def test_public_supporting_serializers_are_read_only(self):
        for serializer_class in (
            PublicCategorySerializer,
            PublicCourseCohortSerializer,
            PublicCourseDeliveryFormatSerializer,
            PublicCourseTeacherSerializer,
            PublicPricingPlanSerializer,
            PublicTagSerializer,
        ):
            serializer = serializer_class()
            self.assertTrue(
                all(field.read_only for field in serializer.fields.values()),
                serializer_class.__name__,
            )
