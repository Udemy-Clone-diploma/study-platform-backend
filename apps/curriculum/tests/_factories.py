"""Shared fixtures for curriculum tests (tests, questions, attempts)."""

from apps.curriculum.models import Lesson, LessonItem, Module, Question, Test
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile, User


def make_student(email="curriculum_student@example.com"):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        role=User.RoleChoices.STUDENT,
    )
    profile = StudentProfile.objects.create(user=user)
    return user, profile


def enroll(student_profile, course):
    return Enrollment.objects.create(student_profile=student_profile, course=course)


def make_module(course, *, order=1, title="Module"):
    return Module.objects.create(course=course, title=title, order=order)


def make_lesson(module, *, order=1, title="Lesson", is_preview=False):
    return Lesson.objects.create(
        module=module,
        title=title,
        order=order,
        is_preview=is_preview,
    )


def make_test(module, *, order=1, **overrides):
    fields = {
        "title": "Quiz",
        "passing_score": 70,
        "allow_retakes": False,
        "max_attempts": None,
        "duration_minutes": None,
    }
    fields.update(overrides)
    return Test.objects.create(module=module, order=order, **fields)


def build_quiz(module, *, order=1, **test_overrides):
    """A four-question test, one of each type, with a known answer key.

    Returns ``(test, {"single", "multi", "tf", "short"})``.
    """
    test = make_test(module, order=order, **test_overrides)
    questions = {
        "single": Question.objects.create(
            test=test,
            order=1,
            question_type=Question.TypeChoices.SINGLE_CHOICE,
            text="What is 2 + 2?",
            options=["3", "4", "5", "6"],
            correct_indices=[1],
        ),
        "multi": Question.objects.create(
            test=test,
            order=2,
            question_type=Question.TypeChoices.MULTIPLE_CHOICE,
            text="Which are prime?",
            options=["2", "4", "7", "9"],
            correct_indices=[0, 2],
        ),
        "tf": Question.objects.create(
            test=test,
            order=3,
            question_type=Question.TypeChoices.TRUE_FALSE,
            text="The sky is blue.",
            correct_bool=True,
        ),
        "short": Question.objects.create(
            test=test,
            order=4,
            question_type=Question.TypeChoices.SHORT_ANSWER,
            text="Capital of France?",
            sample_answer="Paris",
            accepted_answers=["Lutetia"],
        ),
    }
    return test, questions


def all_correct_answers(questions: dict) -> list[dict]:
    """Submission body that scores 100% against ``build_quiz`` questions."""
    return [
        {"question_id": questions["single"].id, "selected_indices": [1]},
        {"question_id": questions["multi"].id, "selected_indices": [0, 2]},
        {"question_id": questions["tf"].id, "answer_bool": True},
        {"question_id": questions["short"].id, "answer_text": "Paris"},
    ]


def attach_test_to_lesson(lesson, test, *, order=1):
    return LessonItem.objects.create(
        lesson=lesson,
        order=order,
        item_type=LessonItem.ItemType.TEST,
        test=test,
    )
