"""Teacher CRUD for tests and questions accepts the new attempt fields.

These endpoints had no test coverage before the attempt system landed.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Question, Test

from ._factories import make_module, make_student


class TestCrudTests(APITestCase):
    def setUp(self):
        self.owner_user, self.owner = make_teacher(email="crud_owner@example.com")
        self.course = make_course(
            self.owner, slug="crud-course", status=Course.StatusChoices.PUBLISHED,
        )
        self.module = make_module(self.course)

    def _tests_url(self):
        return f"/api/v1/courses/{self.course.slug}/modules/{self.module.id}/tests/"

    def _detail_url(self, test):
        return f"{self._tests_url()}{test.id}/"

    def test_owner_creates_test_with_retake_fields(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            self._tests_url(),
            {
                "title": "Final", "passing_score": 80, "duration_minutes": 30,
                "allow_retakes": True, "max_attempts": 3,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["allow_retakes"], True)
        self.assertEqual(response.data["max_attempts"], 3)
        self.assertEqual(response.data["duration_minutes"], 30)
        test = Test.objects.get(id=response.data["id"])
        self.assertTrue(test.allow_retakes)
        self.assertEqual(test.max_attempts, 3)

    def test_retake_fields_default_when_omitted(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(self._tests_url(), {"title": "Basic"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["allow_retakes"])
        self.assertIsNone(response.data["max_attempts"])

    def test_owner_can_patch_test(self):
        self.client.force_authenticate(self.owner_user)
        test = Test.objects.create(module=self.module, order=1, title="Q")
        response = self.client.patch(
            self._detail_url(test),
            {"allow_retakes": True, "max_attempts": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        test.refresh_from_db()
        self.assertTrue(test.allow_retakes)
        self.assertEqual(test.max_attempts, 5)

    def test_owner_can_soft_delete_test(self):
        self.client.force_authenticate(self.owner_user)
        test = Test.objects.create(module=self.module, order=1, title="Q")
        response = self.client.delete(self._detail_url(test))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        test.refresh_from_db()
        self.assertTrue(test.is_deleted)

    def test_non_owner_teacher_forbidden(self):
        _, other = make_teacher(email="crud_other@example.com")
        self.client.force_authenticate(other.user)
        response = self.client.post(self._tests_url(), {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_forbidden(self):
        student_user, _ = make_student(email="crud_student@example.com")
        self.client.force_authenticate(student_user)
        response = self.client.post(self._tests_url(), {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_unauthorized(self):
        response = self.client.post(self._tests_url(), {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class QuestionCrudTests(APITestCase):
    def setUp(self):
        self.owner_user, self.owner = make_teacher(email="qcrud_owner@example.com")
        self.course = make_course(
            self.owner, slug="qcrud-course", status=Course.StatusChoices.PUBLISHED,
        )
        self.module = make_module(self.course)
        self.test = Test.objects.create(module=self.module, order=1, title="Quiz")

    def questions_url(self):
        return (
            f"/api/v1/courses/{self.course.slug}/modules/{self.module.id}"
            f"/tests/{self.test.id}/questions/"
        )

    def test_owner_creates_single_choice_question_with_indices(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            self.questions_url(),
            {
                "question_type": "single_choice",
                "text": "2+2?", "options": ["3", "4", "5"],
                "correct_indices": [1],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["correct_indices"], [1])
        self.assertNotIn("correct_index", response.data)
        question = Question.objects.get(id=response.data["id"])
        self.assertEqual(question.correct_indices, [1])

    def test_owner_creates_short_answer_with_accepted_answers(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post(
            self.questions_url(),
            {
                "question_type": "short_answer",
                "text": "Capital?", "sample_answer": "Paris",
                "accepted_answers": ["Lutetia", "City of Light"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["accepted_answers"], ["Lutetia", "City of Light"])

    def test_owner_can_patch_question_answer_key(self):
        self.client.force_authenticate(self.owner_user)
        question = Question.objects.create(
            test=self.test, order=1,
            question_type=Question.TypeChoices.MULTIPLE_CHOICE,
            text="pick", options=["a", "b", "c"], correct_indices=[0],
        )
        response = self.client.patch(
            f"{self.questions_url()}{question.id}/",
            {"correct_indices": [0, 2]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question.refresh_from_db()
        self.assertEqual(question.correct_indices, [0, 2])

    def test_student_forbidden_to_create_question(self):
        student_user, _ = make_student(email="qcrud_student@example.com")
        self.client.force_authenticate(student_user)
        response = self.client.post(
            self.questions_url(), {"text": "x"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
