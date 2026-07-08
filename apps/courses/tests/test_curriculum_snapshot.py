"""Course copy + pending-edit draft cloning must carry the test/question answer
key and retake config, and merging a draft back onto the live course must
preserve existing row ids (student progress FK stability) while still picking
up new/removed content.
"""

from django.test import TestCase

from apps.courses.models import Course
from apps.courses.services.course_service import CourseService
from apps.courses.services.pending_edit_service import PendingEditService
from apps.curriculum.models import Lesson, Module, Question, Test

from ._factories import make_course, make_teacher


def _build_module_with_quiz(course):
    module = Module.objects.create(course=course, title="M", order=1)
    test = Test.objects.create(
        module=module, order=1, title="Quiz", passing_score=80,
        duration_minutes=20, allow_retakes=True, max_attempts=4,
    )
    Question.objects.create(
        test=test, order=1, question_type=Question.TypeChoices.MULTIPLE_CHOICE,
        text="pick", options=["a", "b", "c"], correct_indices=[0, 2],
    )
    Question.objects.create(
        test=test, order=2, question_type=Question.TypeChoices.SHORT_ANSWER,
        text="cap?", sample_answer="Paris", accepted_answers=["Lutetia"],
    )
    return module, test


class CopyToDraftCarryoverTests(TestCase):
    def test_copy_carries_retake_config_and_answer_key(self):
        _, owner = make_teacher(email="copy_owner@example.com")
        course = make_course(owner, slug="copy-src", status=Course.StatusChoices.PUBLISHED)
        _build_module_with_quiz(course)

        draft = CourseService.copy_to_draft(course, owner)

        copied = Test.objects.get(module__course=draft)
        self.assertEqual(copied.duration_minutes, 20)
        self.assertTrue(copied.allow_retakes)
        self.assertEqual(copied.max_attempts, 4)

        questions = list(Question.objects.filter(test=copied).order_by("order"))
        self.assertEqual(questions[0].correct_indices, [0, 2])
        self.assertEqual(questions[1].accepted_answers, ["Lutetia"])


class PendingEditCloneTests(TestCase):
    def test_clone_carries_retake_config_answer_key_and_source_ids(self):
        _, owner = make_teacher(email="clone_owner@example.com")
        course = make_course(owner, slug="clone-src", status=Course.StatusChoices.PUBLISHED)
        _, original_test = _build_module_with_quiz(course)

        draft = CourseService.clone_for_pending_edit(course)

        cloned = Test.objects.get(module__course=draft)
        self.assertEqual(cloned.duration_minutes, 20)
        self.assertTrue(cloned.allow_retakes)
        self.assertEqual(cloned.max_attempts, 4)
        self.assertEqual(cloned.source_test_id, original_test.id)

        questions = list(Question.objects.filter(test=cloned).order_by("order"))
        self.assertEqual(questions[0].correct_indices, [0, 2])
        self.assertEqual(questions[1].accepted_answers, ["Lutetia"])


class PendingEditMergeTests(TestCase):
    def test_merge_updates_existing_lesson_in_place_preserving_id(self):
        _, owner = make_teacher(email="merge_owner1@example.com")
        course = make_course(owner, slug="merge-src-1", status=Course.StatusChoices.PUBLISHED)
        module = Module.objects.create(course=course, title="M", order=1)
        lesson = Lesson.objects.create(module=module, title="Original title", order=1)
        original_lesson_id = lesson.id

        pending_edit = PendingEditService.get_or_create(course)
        draft_lesson = Lesson.objects.get(source_lesson_id=original_lesson_id)
        draft_lesson.title = "Edited title"
        draft_lesson.save()

        PendingEditService.merge_into_live(pending_edit)

        live_lesson = Lesson.objects.get(id=original_lesson_id)
        self.assertEqual(live_lesson.title, "Edited title")
        self.assertFalse(live_lesson.is_deleted)

    def test_merge_creates_new_lesson_and_soft_deletes_removed_one(self):
        _, owner = make_teacher(email="merge_owner2@example.com")
        course = make_course(owner, slug="merge-src-2", status=Course.StatusChoices.PUBLISHED)
        module = Module.objects.create(course=course, title="M", order=1)
        kept_lesson = Lesson.objects.create(module=module, title="Kept", order=1)
        removed_lesson = Lesson.objects.create(module=module, title="Removed", order=2)

        pending_edit = PendingEditService.get_or_create(course)
        draft_module = Module.objects.get(source_module_id=module.id)

        # Teacher deletes one lesson in the draft and adds a brand-new one.
        Lesson.objects.filter(source_lesson_id=removed_lesson.id).update(is_deleted=True)
        Lesson.objects.create(module=draft_module, title="Brand new", order=2)

        PendingEditService.merge_into_live(pending_edit)

        kept = Lesson.objects.get(id=kept_lesson.id)
        self.assertFalse(kept.is_deleted)

        removed = Lesson.all_objects.get(id=removed_lesson.id)
        self.assertTrue(removed.is_deleted)

        new_titles = set(
            Lesson.objects.filter(module=module).exclude(id=kept_lesson.id).values_list("title", flat=True)
        )
        self.assertEqual(new_titles, {"Brand new"})
