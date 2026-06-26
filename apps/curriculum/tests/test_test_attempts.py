"""Submit + grade endpoint: POST/GET /courses/<slug>/tests/<id>/attempts/."""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Test, TestAttempt
from apps.users.models import User

from ._factories import (
    all_correct_answers,
    build_quiz,
    enroll,
    make_lesson,
    make_module,
    make_student,
)


class AttemptTestBase(APITestCase):
    def setUp(self):
        self.owner_user, self.owner = make_teacher(email="att_owner@example.com")
        self.course = make_course(
            self.owner, slug="att-course", status=Course.StatusChoices.PUBLISHED,
        )
        self.module = make_module(self.course)
        self.lesson = make_lesson(self.module)
        self.test, self.questions = build_quiz(self.module)
        self.student_user, self.profile = make_student(email="att_student@example.com")
        enroll(self.profile, self.course)

    def url(self, test=None):
        test = test or self.test
        return f"/api/v1/courses/{self.course.slug}/tests/{test.id}/attempts/"

    def submit(self, answers, *, test=None, user=None):
        self.client.force_authenticate(user or self.student_user)
        return self.client.post(self.url(test), {"answers": answers}, format="json")

    def by_id(self, result):
        return {q["id"]: q for q in result["questions"]}


class AttemptPermissionTests(AttemptTestBase):
    def test_anonymous_is_unauthorized(self):
        self.client.force_authenticate(None)
        response = self.client.post(self.url(), {"answers": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_enrolled_student_is_forbidden(self):
        other_user, _ = make_student(email="att_nonenrolled@example.com")
        response = self.submit(all_correct_answers(self.questions), user=other_user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_teacher_not_enrolled_is_forbidden(self):
        response = self.submit(all_correct_answers(self.questions), user=self.owner_user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_test_returns_404(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            f"/api/v1/courses/{self.course.slug}/tests/999999/attempts/",
            {"answers": []}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_answers_key_is_bad_request(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(self.url(), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AttemptGradingTests(AttemptTestBase):
    def test_all_correct_scores_100_and_passes(self):
        response = self.submit(all_correct_answers(self.questions))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        d = response.data
        self.assertEqual(d["score"], 100)
        self.assertTrue(d["passed"])
        self.assertEqual(d["correct_count"], 4)
        self.assertEqual(d["total_count"], 4)
        self.assertEqual(d["attempt_number"], 1)
        self.assertEqual(d["attempts_used"], 1)
        self.assertEqual(d["passing_score"], 70)
        self.assertTrue(TestAttempt.objects.filter(test=self.test, score=100).exists())

    def test_result_echoes_submission_and_reveals_answers(self):
        d = self.submit(all_correct_answers(self.questions)).data
        q = self.by_id(d)
        single = q[self.questions["single"].id]
        self.assertEqual(single["selected_indices"], [1])
        self.assertEqual(single["correct_indices"], [1])
        self.assertTrue(single["is_correct"])
        tf = q[self.questions["tf"].id]
        self.assertEqual(tf["answer_bool"], True)
        self.assertEqual(tf["correct_bool"], True)
        short = q[self.questions["short"].id]
        self.assertEqual(short["answer_text"], "Paris")
        self.assertEqual(short["sample_answer"], "Paris")

    def test_partial_score_fails(self):
        answers = [{"question_id": self.questions["single"].id, "selected_indices": [1]}]
        d = self.submit(answers).data
        self.assertEqual(d["score"], 25)  # 1 of 4
        self.assertFalse(d["passed"])
        self.assertEqual(d["correct_count"], 1)

    def test_missing_question_is_graded_incorrect(self):
        answers = all_correct_answers(self.questions)
        answers = [a for a in answers if a["question_id"] != self.questions["tf"].id]
        d = self.submit(answers).data
        self.assertFalse(self.by_id(d)[self.questions["tf"].id]["is_correct"])
        self.assertEqual(d["correct_count"], 3)

    def test_multiple_choice_is_all_or_nothing(self):
        test, questions = build_quiz(self.module, order=2, allow_retakes=True)
        for selection, expected in (([0], False), ([0, 1, 2], False), ([2, 0], True)):
            answers = [{"question_id": questions["multi"].id, "selected_indices": selection}]
            d = self.submit(answers, test=test).data
            self.assertEqual(
                self.by_id(d)[questions["multi"].id]["is_correct"], expected,
                msg=f"selection {selection}",
            )

    def test_true_false_wrong_answer_is_incorrect(self):
        answers = [{"question_id": self.questions["tf"].id, "answer_bool": False}]
        d = self.submit(answers).data
        self.assertFalse(self.by_id(d)[self.questions["tf"].id]["is_correct"])

    def test_short_answer_is_normalized_and_matches_accepted(self):
        test, questions = build_quiz(self.module, order=2, allow_retakes=True)
        for text in ("  paris ", "PARIS", "lutetia"):
            answers = [{"question_id": questions["short"].id, "answer_text": text}]
            d = self.submit(answers, test=test).data
            self.assertTrue(
                self.by_id(d)[questions["short"].id]["is_correct"], msg=text,
            )

    def test_short_answer_wrong_is_incorrect(self):
        answers = [{"question_id": self.questions["short"].id, "answer_text": "Berlin"}]
        d = self.submit(answers).data
        self.assertFalse(self.by_id(d)[self.questions["short"].id]["is_correct"])

    def test_passing_threshold_is_inclusive(self):
        test, questions = build_quiz(self.module, order=2, passing_score=50)
        answers = [
            {"question_id": questions["single"].id, "selected_indices": [1]},
            {"question_id": questions["tf"].id, "answer_bool": True},
        ]
        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            self.url(test), {"answers": answers}, format="json",
        )
        self.assertEqual(response.data["score"], 50)
        self.assertTrue(response.data["passed"])

    def test_zero_question_test_is_conflict(self):
        empty = Test.objects.create(module=self.module, order=3, title="Empty")
        self.client.force_authenticate(self.student_user)
        response = self.client.post(self.url(empty), {"answers": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class AttemptRetakeTests(AttemptTestBase):
    def test_single_attempt_when_retakes_disabled(self):
        first = self.submit(all_correct_answers(self.questions))
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertFalse(first.data["can_retake"])

        second = self.submit(all_correct_answers(self.questions))
        self.assertEqual(second.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(TestAttempt.objects.filter(test=self.test).count(), 1)

    def test_max_attempts_cap_is_enforced(self):
        test, questions = build_quiz(
            self.module, order=2, allow_retakes=True, max_attempts=2,
        )
        self.client.force_authenticate(self.student_user)
        body = {"answers": all_correct_answers(questions)}

        r1 = self.client.post(self.url(test), body, format="json")
        r2 = self.client.post(self.url(test), body, format="json")
        r3 = self.client.post(self.url(test), body, format="json")

        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.data["attempt_number"], 2)
        self.assertFalse(r2.data["can_retake"])
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)

    def test_unlimited_retakes_increment_attempt_number(self):
        test, questions = build_quiz(
            self.module, order=2, allow_retakes=True, max_attempts=None,
        )
        self.client.force_authenticate(self.student_user)
        body = {"answers": all_correct_answers(questions)}
        numbers = [
            self.client.post(self.url(test), body, format="json").data["attempt_number"]
            for _ in range(3)
        ]
        self.assertEqual(numbers, [1, 2, 3])
        self.assertTrue(
            self.client.post(self.url(test), body, format="json").data["can_retake"]
        )


class AttemptHistoryTests(AttemptTestBase):
    def test_history_is_paginated_and_reflects_attempts(self):
        self.test.allow_retakes = True
        self.test.save(update_fields=["allow_retakes"])
        self.submit(all_correct_answers(self.questions))
        self.submit(all_correct_answers(self.questions))

        self.client.force_authenticate(self.student_user)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()), {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 2)
        first = response.data["results"][0]
        self.assertEqual(set(first.keys()), {"id", "attempt_number", "score", "passed", "submitted_at"})

    def test_history_only_returns_own_attempts(self):
        self.submit(all_correct_answers(self.questions))
        other_user, other_profile = make_student(email="att_other@example.com")
        enroll(other_profile, self.course)
        self.client.force_authenticate(other_user)
        response = self.client.get(self.url())
        self.assertEqual(response.data["count"], 0)

    def test_last_attempt_reflected_in_lesson_detail(self):
        from ._factories import attach_test_to_lesson
        attach_test_to_lesson(self.lesson, self.test)
        self.submit(all_correct_answers(self.questions))

        self.client.force_authenticate(self.student_user)
        response = self.client.get(
            f"/api/v1/courses/{self.course.slug}/lessons/{self.lesson.id}/"
        )
        test_item = next(i for i in response.data["items"] if i["item_type"] == "test")
        test_obj = test_item["test"]
        self.assertEqual(test_obj["attempts_used"], 1)
        self.assertFalse(test_obj["can_attempt"])  # retakes disabled
        self.assertEqual(test_obj["last_attempt"]["score"], 100)
        self.assertTrue(test_obj["last_attempt"]["passed"])
