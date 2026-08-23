"""A student loading a lesson must never receive the test answer key.

Mirrors the frontend's security requirement: GET the lesson, look at
items[].test.questions[] - the answer fields must be absent for students
(and anyone who is not the teacher/owner/staff), present for authors.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.users.models import User

from ._factories import (
    attach_test_to_lesson,
    build_quiz,
    enroll,
    make_lesson,
    make_module,
    make_student,
)

ANSWER_FIELDS = {"correct_indices", "correct_bool", "sample_answer", "accepted_answers"}
STUDENT_FIELDS = {"id", "question_type", "text", "options", "order"}
ENRICHMENT_FIELDS = {"attempts_used", "can_attempt", "last_attempt"}


class LessonTestVisibilityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_user, cls.owner = make_teacher(email="vis_owner@example.com")
        cls.course = make_course(
            cls.owner, slug="vis-course", status=Course.StatusChoices.PUBLISHED,
        )
        cls.module = make_module(cls.course)
        cls.locked_lesson = make_lesson(cls.module, order=1, is_preview=False)
        cls.preview_lesson = make_lesson(cls.module, order=2, is_preview=True)
        cls.test, cls.questions = build_quiz(cls.module)
        attach_test_to_lesson(cls.locked_lesson, cls.test)
        # A second test on the preview lesson so anonymous access can be checked.
        cls.preview_test, _ = build_quiz(cls.module, order=2)
        attach_test_to_lesson(cls.preview_lesson, cls.preview_test)

    def _url(self, lesson):
        return f"/api/v1/courses/{self.course.slug}/lessons/{lesson.id}/"

    def _test_item(self, response):
        items = response.data["items"]
        test_item = next(i for i in items if i["item_type"] == "test")
        return test_item["test"]


    def test_enrolled_student_does_not_receive_answer_fields(self):
        student_user, profile = make_student(email="vis_student@example.com")
        enroll(profile, self.course)
        self.client.force_authenticate(student_user)

        response = self.client.get(self._url(self.locked_lesson))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        questions = self._test_item(response)["questions"]
        self.assertEqual(len(questions), 4)
        for q in questions:
            self.assertEqual(set(q.keys()), STUDENT_FIELDS)
            for field in ANSWER_FIELDS:
                self.assertNotIn(field, q)

    def test_anonymous_on_preview_lesson_does_not_receive_answer_fields(self):
        response = self.client.get(self._url(self.preview_lesson))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for q in self._test_item(response)["questions"]:
            self.assertEqual(set(q.keys()), STUDENT_FIELDS)

    def test_non_owner_teacher_on_preview_lesson_does_not_receive_answers(self):
        _, other = make_teacher(email="vis_other_teacher@example.com")
        self.client.force_authenticate(other.user)
        response = self.client.get(self._url(self.preview_lesson))
        for q in self._test_item(response)["questions"]:
            self.assertNotIn("correct_indices", q)


    def test_owner_teacher_receives_answer_fields(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.get(self._url(self.locked_lesson))
        single = next(
            q for q in self._test_item(response)["questions"]
            if q["question_type"] == "single_choice"
        )
        self.assertEqual(single["correct_indices"], [1])
        short = next(
            q for q in self._test_item(response)["questions"]
            if q["question_type"] == "short_answer"
        )
        self.assertEqual(short["sample_answer"], "Paris")
        self.assertEqual(short["accepted_answers"], ["Lutetia"])

    def test_admin_receives_answer_fields(self):
        admin = User.objects.create_user(
            email="vis_admin@example.com", password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(admin)
        response = self.client.get(self._url(self.locked_lesson))
        for q in self._test_item(response)["questions"]:
            self.assertIn("question_type", q)
        self.assertTrue(
            any("correct_indices" in q for q in self._test_item(response)["questions"])
        )

    def test_moderator_receives_answer_fields(self):
        moderator = User.objects.create_user(
            email="vis_mod@example.com", password="pass12345",
            role=User.RoleChoices.MODERATOR,
        )
        self.client.force_authenticate(moderator)
        response = self.client.get(self._url(self.locked_lesson))
        self.assertTrue(
            any("correct_bool" in q for q in self._test_item(response)["questions"])
        )


    def test_enrolled_student_gets_attempt_status_enrichment(self):
        student_user, profile = make_student(email="vis_enrich@example.com")
        enroll(profile, self.course)
        self.client.force_authenticate(student_user)

        test_obj = self._test_item(self.client.get(self._url(self.locked_lesson)))
        self.assertEqual(test_obj["attempts_used"], 0)
        self.assertTrue(test_obj["can_attempt"])
        self.assertIsNone(test_obj["last_attempt"])
        # static config is visible to students too
        self.assertIn("allow_retakes", test_obj)
        self.assertIn("max_attempts", test_obj)

    def test_teacher_does_not_get_attempt_status_enrichment(self):
        self.client.force_authenticate(self.owner_user)
        test_obj = self._test_item(self.client.get(self._url(self.locked_lesson)))
        for field in ENRICHMENT_FIELDS:
            self.assertNotIn(field, test_obj)

    def test_zero_question_test_is_not_attemptable(self):
        empty_lesson = make_lesson(self.module, order=3, is_preview=False)
        empty_test = self.test.__class__.objects.create(
            module=self.module, order=3, title="Empty",
        )
        attach_test_to_lesson(empty_lesson, empty_test)
        student_user, profile = make_student(email="vis_empty@example.com")
        enroll(profile, self.course)
        self.client.force_authenticate(student_user)

        test_obj = self._test_item(self.client.get(self._url(empty_lesson)))
        self.assertEqual(test_obj["attempts_used"], 0)
        self.assertFalse(test_obj["can_attempt"])
