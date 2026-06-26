"""Course copy + pending-edit snapshots must carry the test/question answer
key and retake config. Regression guard: these paths reference the curriculum
Question/Test models, and previously had no coverage that included questions.
"""

from django.test import TestCase

from apps.courses.models import Course
from apps.courses.services.course_service import CourseService
from apps.courses.services.pending_edit_service import PendingEditService
from apps.curriculum.models import Module, Question, Test

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


class PendingEditSnapshotCarryoverTests(TestCase):
    def test_snapshot_serializes_new_fields_without_legacy_key(self):
        _, owner = make_teacher(email="snap_owner@example.com")
        course = make_course(owner, slug="snap-src", status=Course.StatusChoices.PUBLISHED)
        _build_module_with_quiz(course)

        snapshot = PendingEditService._build_modules_snapshot(course)
        test_snap = snapshot[0]["tests"][0]

        self.assertEqual(test_snap["allow_retakes"], True)
        self.assertEqual(test_snap["max_attempts"], 4)
        self.assertEqual(test_snap["duration_minutes"], 20)
        question_snap = test_snap["questions"][0]
        self.assertEqual(question_snap["correct_indices"], [0, 2])
        self.assertNotIn("correct_index", question_snap)
        self.assertEqual(test_snap["questions"][1]["accepted_answers"], ["Lutetia"])

    def test_apply_snapshot_restores_new_fields(self):
        _, owner = make_teacher(email="apply_owner@example.com")
        source = make_course(owner, slug="apply-src", status=Course.StatusChoices.PUBLISHED)
        _build_module_with_quiz(source)
        snapshot = PendingEditService._build_modules_snapshot(source)

        target = make_course(owner, slug="apply-tgt", status=Course.StatusChoices.DRAFT)
        PendingEditService._apply_modules_snapshot(target, snapshot)

        applied = Test.objects.get(module__course=target)
        self.assertTrue(applied.allow_retakes)
        self.assertEqual(applied.max_attempts, 4)
        questions = list(Question.objects.filter(test=applied).order_by("order"))
        self.assertEqual(questions[0].correct_indices, [0, 2])
        self.assertEqual(questions[1].accepted_answers, ["Lutetia"])

    def test_apply_tolerates_legacy_correct_index_snapshot(self):
        _, owner = make_teacher(email="legacy_owner@example.com")
        target = make_course(owner, slug="legacy-tgt", status=Course.StatusChoices.DRAFT)
        legacy_snapshot = [{
            "title": "M", "description": "", "order": 1, "lessons": [],
            "tests": [{
                "title": "T", "description": "", "passing_score": 70, "order": 1,
                "questions": [{
                    "question_type": "single_choice", "text": "q",
                    "options": ["x", "y"], "correct_index": 1, "order": 1,
                }],
            }],
        }]

        PendingEditService._apply_modules_snapshot(target, legacy_snapshot)

        question = Question.objects.get(test__module__course=target)
        self.assertEqual(question.correct_indices, [1])
