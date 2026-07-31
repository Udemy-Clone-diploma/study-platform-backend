from django.test import SimpleTestCase

from apps.curriculum.serializers import (
    PublicCourseLessonSerializer,
    PublicCourseModuleSerializer,
)


class PublicCurriculumSerializerContractTests(SimpleTestCase):
    def test_public_module_contains_only_lesson_summaries(self):
        serializer = PublicCourseModuleSerializer()

        self.assertEqual(
            list(serializer.fields),
            ["id", "title", "description", "order", "lessons"],
        )
        self.assertIsInstance(
            serializer.fields["lessons"].child,
            PublicCourseLessonSerializer,
        )
        self.assertTrue({"tests", "source_module_id"}.isdisjoint(serializer.fields))

    def test_public_lesson_excludes_content_and_runtime_access_data(self):
        serializer = PublicCourseLessonSerializer()

        self.assertEqual(
            list(serializer.fields),
            [
                "id",
                "title",
                "order",
                "duration_minutes",
                "is_preview",
                "unlock_after_days",
                "requires_previous",
                "is_mandatory",
            ],
        )
        self.assertTrue(
            {
                "min_score",
                "meeting_url",
                "is_manually_locked",
                "documents",
                "items",
                "tests",
                "source_lesson_id",
            }.isdisjoint(serializer.fields)
        )
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))
