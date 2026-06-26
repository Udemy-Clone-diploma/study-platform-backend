from django.db import IntegrityError, transaction

from apps.curriculum.exceptions import RetakeNotAllowedError, TestNotAttemptableError
from apps.curriculum.models import Question, Test, TestAttempt
from apps.users.models import StudentProfile

CHOICE_TYPES = (Question.TypeChoices.SINGLE_CHOICE, Question.TypeChoices.MULTIPLE_CHOICE)


class TestAttemptService:
    @staticmethod
    def attempts_used(student_profile: StudentProfile, test: Test) -> int:
        return TestAttempt.objects.filter(
            student_profile=student_profile, test=test,
        ).count()

    @staticmethod
    def can_attempt(test: Test, attempts_used: int, question_count: int | None = None) -> bool:
        if question_count is None:
            question_count = test.questions.count()
        if question_count == 0:
            return False
        if attempts_used == 0:
            return True
        if not test.allow_retakes:
            return False
        if test.max_attempts is not None and attempts_used >= test.max_attempts:
            return False
        return True

    @staticmethod
    def last_attempt(student_profile: StudentProfile, test: Test) -> TestAttempt | None:
        return (
            TestAttempt.objects.filter(student_profile=student_profile, test=test)
            .order_by("-attempt_number")
            .first()
        )

    @classmethod
    def submit(cls, student_profile: StudentProfile, test: Test, answers: list[dict]) -> dict:
        questions = list(test.questions.all())
        question_count = len(questions)
        if question_count == 0:
            raise TestNotAttemptableError("This test has no questions and cannot be taken.")

        attempts_used = cls.attempts_used(student_profile, test)
        if not cls.can_attempt(test, attempts_used, question_count):
            raise RetakeNotAllowedError("You have used all of your attempts for this test.")

        graded, correct_count = cls._grade(questions, answers)
        score = round(correct_count / question_count * 100)
        passed = score >= test.passing_score
        attempt = cls._create_attempt(
            student_profile, test, score, passed, answers, question_count,
        )

        return cls._build_result(attempt, graded, correct_count, question_count)

    @classmethod
    def result_for_attempt(cls, attempt: TestAttempt) -> dict:
        """Rebuild the graded-detail payload for a stored attempt.

        Per-question correctness and the revealed answer key are re-derived from the
        test's current questions; the attempt's stored score/passed stay authoritative.
        """
        questions = list(attempt.test.questions.all())
        graded, correct_count = cls._grade(questions, attempt.answers)
        return cls._build_result(attempt, graded, correct_count, len(questions))

    @classmethod
    def _grade(cls, questions: list, answers: list[dict]) -> tuple[list, int]:
        answers_by_qid = {a["question_id"]: a for a in answers}
        graded = []
        correct_count = 0
        for question in questions:
            submitted = answers_by_qid.get(question.id, {})
            is_correct = cls._grade_question(question, submitted)
            correct_count += int(is_correct)
            graded.append((question, submitted, is_correct))
        return graded, correct_count

    @classmethod
    def _build_result(
        cls, attempt: TestAttempt, graded: list, correct_count: int, question_count: int,
    ) -> dict:
        test = attempt.test
        attempts_used = cls.attempts_used(attempt.student_profile, test)
        return {
            "attempt_id": attempt.id,
            "attempt_number": attempt.attempt_number,
            "score": attempt.score,
            "correct_count": correct_count,
            "total_count": question_count,
            "passed": attempt.passed,
            "passing_score": test.passing_score,
            "can_retake": cls.can_attempt(test, attempts_used, question_count),
            "attempts_used": attempts_used,
            "max_attempts": test.max_attempts,
            "questions": [
                cls._question_result(question, submitted, is_correct)
                for question, submitted, is_correct in graded
            ],
        }

    @classmethod
    def _create_attempt(
        cls,
        student_profile: StudentProfile,
        test: Test,
        score: int,
        passed: bool,
        answers: list[dict],
        question_count: int,
    ) -> TestAttempt:
        # Allocate the next attempt number, retrying if a concurrent submit grabs it.
        for _ in range(5):
            attempts_used = cls.attempts_used(student_profile, test)
            if not cls.can_attempt(test, attempts_used, question_count):
                raise RetakeNotAllowedError(
                    "You have used all of your attempts for this test."
                )
            try:
                with transaction.atomic():
                    return TestAttempt.objects.create(
                        student_profile=student_profile,
                        test=test,
                        attempt_number=attempts_used + 1,
                        score=score,
                        passed=passed,
                        answers=answers,
                    )
            except IntegrityError:
                continue
        raise RetakeNotAllowedError("Could not record the attempt, please retry.")

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(str(text).strip().lower().split())

    @classmethod
    def _grade_question(cls, question: Question, submitted: dict) -> bool:
        if question.question_type in CHOICE_TYPES:
            selected = submitted.get("selected_indices")
            if not selected:
                return False
            return set(selected) == set(question.correct_indices or [])

        if question.question_type == Question.TypeChoices.TRUE_FALSE:
            answer_bool = submitted.get("answer_bool")
            if answer_bool is None:
                return False
            return answer_bool == question.correct_bool

        if question.question_type == Question.TypeChoices.SHORT_ANSWER:
            answer_text = submitted.get("answer_text")
            if not answer_text:
                return False
            acceptable = [question.sample_answer, *(question.accepted_answers or [])]
            normalized = cls._normalize(answer_text)
            return any(
                normalized == cls._normalize(candidate)
                for candidate in acceptable
                if candidate
            )

        return False

    @staticmethod
    def _question_result(question: Question, submitted: dict, is_correct: bool) -> dict:
        result = {
            "id": question.id,
            "question_type": question.question_type,
            "text": question.text,
            "options": question.options,
            "order": question.order,
            "is_correct": is_correct,
        }
        if question.question_type in CHOICE_TYPES:
            result["selected_indices"] = submitted.get("selected_indices") or []
            result["correct_indices"] = question.correct_indices or []
        elif question.question_type == Question.TypeChoices.TRUE_FALSE:
            result["answer_bool"] = submitted.get("answer_bool")
            result["correct_bool"] = question.correct_bool
        elif question.question_type == Question.TypeChoices.SHORT_ANSWER:
            result["answer_text"] = submitted.get("answer_text") or ""
            result["sample_answer"] = question.sample_answer
            result["accepted_answers"] = question.accepted_answers or []
        return result
