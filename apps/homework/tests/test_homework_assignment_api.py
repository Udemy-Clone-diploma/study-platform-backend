import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.tests._factories import make_course, make_teacher
from apps.courses.models import Cohort, CohortMember, CourseDeliveryFormat
from apps.curriculum.models import Lesson, Module, Question, Test, TestAttempt
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
)


class HomeworkAssignmentApiTests(APITestCase):
    def setUp(self):
        self._media_dir = tempfile.TemporaryDirectory()
        self._media_override = override_settings(MEDIA_ROOT=self._media_dir.name)
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        self.addCleanup(self._media_dir.cleanup)
        self.teacher, teacher_profile = make_teacher()
        self.course = make_course(teacher_profile, slug="homework-course")
        self.module = Module.objects.create(
            course=self.course,
            title="Module 1",
            order=1,
        )
        self.url = reverse("homework-assignment-list", args=[self.course.slug])
        self.student, self.student_profile = make_student(email="homework_student@example.com")
        self.other_student, self.other_student_profile = make_student(
            email="other_homework_student@example.com"
        )
        self.student_enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.other_student_enrollment = Enrollment.objects.create(
            student_profile=self.other_student_profile,
            course=self.course,
        )

    def test_course_owner_can_create_a_homework_draft(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Build a portfolio page",
                "description": "Create a responsive page and submit its URL.",
                "module": self.module.id,
                "due_at": "2026-07-01T12:00:00Z",
                "max_score": 100,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = HomeworkAssignment.objects.get()
        self.assertEqual(assignment.course, self.course)
        self.assertEqual(assignment.module, self.module)
        self.assertEqual(assignment.created_by, self.teacher)
        self.assertEqual(assignment.status, HomeworkAssignment.StatusChoices.DRAFT)
        self.assertEqual(response.data["course_id"], self.course.id)
        self.assertEqual(response.data["course_slug"], self.course.slug)

    def test_course_owner_can_attach_course_test_to_homework(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Lesson quiz",
            description="Check the basics.",
            passing_score=80,
            order=1,
        )
        Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.TRUE_FALSE,
            text="The portfolio must be responsive.",
            correct_bool=True,
            order=1,
        )
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Complete the quiz",
                "description": "Answer the quiz questions.",
                "module": self.module.id,
                "lesson": lesson.id,
                "test": test.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["test"], test.id)
        self.assertEqual(response.data["test_detail"]["title"], "Lesson quiz")
        self.assertEqual(len(response.data["test_detail"]["questions"]), 1)

    def test_homework_with_test_does_not_require_description(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Description-free quiz",
            passing_score=80,
            order=1,
        )
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Complete the quiz",
                "module": self.module.id,
                "lesson": lesson.id,
                "test": test.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = HomeworkAssignment.objects.get(pk=response.data["id"])
        self.assertEqual(assignment.description, "")
        self.assertEqual(assignment.test, test)

    def test_course_owner_can_reuse_previous_homework_as_template(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Reusable quiz",
            passing_score=70,
            order=1,
        )
        source = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            lesson=lesson,
            test=test,
            created_by=self.teacher,
            title="Original homework",
            description="Use this task again.",
            max_score=20,
        )
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {"source_assignment": source.id, "due_at": "2026-07-02T12:00:00Z"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = HomeworkAssignment.objects.get(pk=response.data["id"])
        self.assertEqual(assignment.source_assignment, source)
        self.assertEqual(assignment.title, source.title)
        self.assertEqual(assignment.description, source.description)
        self.assertEqual(assignment.lesson, lesson)
        self.assertEqual(assignment.test, test)
        self.assertEqual(assignment.max_score, 20)

    def test_other_teacher_cannot_create_a_homework_draft(self):
        other_teacher, _ = make_teacher(email="other@example.com")
        self.client.force_authenticate(other_teacher)

        response = self.client.post(
            self.url,
            {"title": "Unauthorized", "description": "This must not be created."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(HomeworkAssignment.objects.exists())

    def test_max_score_must_be_positive(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            self.url,
            {"title": "Invalid score", "description": "Test", "max_score": 0},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_score", response.data)

    def test_teacher_publishes_to_selected_student_and_reviews_submission(self):
        self.client.force_authenticate(self.teacher)
        create_response = self.client.post(
            self.url,
            {
                "module": self.module.id,
                "title": "Submit a responsive page",
                "description": "Share the deployed URL and a short explanation.",
                "max_score": 10,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        assignment_id = create_response.data["id"]

        assignment_attachment_response = self.client.post(
            reverse(
                "homework-assignment-attachment-list",
                args=[self.course.slug, assignment_id],
            ),
            {"file": SimpleUploadedFile("requirements.pdf", b"test document")},
            format="multipart",
        )
        self.assertEqual(assignment_attachment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(assignment_attachment_response.data["original_name"], "requirements.pdf")

        publish_response = self.client.post(
            reverse("homework-assignment-publish", args=[self.course.slug, assignment_id]),
            {"enrollment_ids": [self.student_enrollment.id]},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(publish_response.data["status"], HomeworkAssignment.StatusChoices.PUBLISHED)

        self.client.force_authenticate(self.student)
        assigned_response = self.client.get(reverse("student-homework-list"))
        self.assertEqual(assigned_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in assigned_response.data], [assignment_id])
        self.assertEqual(assigned_response.data[0]["recipients"], [])
        self.assertEqual(assigned_response.data[0]["attachments"][0]["original_name"], "requirements.pdf")

        submission_attachment_response = self.client.post(
            reverse("student-homework-submission-attachment-list", args=[assignment_id]),
            {"file": SimpleUploadedFile("solution.zip", b"student work")},
            format="multipart",
        )
        self.assertEqual(submission_attachment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            submission_attachment_response.data["attachments"][0]["original_name"],
            "solution.zip",
        )

        submission_response = self.client.post(
            reverse("student-homework-submission", args=[assignment_id]),
            {"content": "https://example.com/my-responsive-page"},
            format="json",
        )
        self.assertEqual(submission_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submission_response.data["attachments"][0]["original_name"], "solution.zip")

        self.client.force_authenticate(self.other_student)
        other_assigned_response = self.client.get(reverse("student-homework-list"))
        self.assertEqual(other_assigned_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_assigned_response.data, [])

        self.client.force_authenticate(self.teacher)
        review_response = self.client.patch(
            reverse(
                "homework-submission-review",
                args=[self.course.slug, assignment_id, submission_response.data["id"]],
            ),
            {"score": 9, "feedback": "Good work. Improve the mobile navigation."},
            format="json",
        )
        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(review_response.data["status"], "reviewed")
        self.assertEqual(review_response.data["score"], 9)
        self.assertEqual(review_response.data["attachments"][0]["original_name"], "solution.zip")

        direct_edit_response = self.client.patch(
            reverse(
                "homework-submission-review",
                args=[self.course.slug, assignment_id, submission_response.data["id"]],
            ),
            {"score": 10, "feedback": "Edited without retrieve."},
            format="json",
        )
        self.assertEqual(direct_edit_response.status_code, status.HTTP_409_CONFLICT)

        retrieve_response = self.client.post(
            reverse(
                "homework-submission-retrieve",
                args=[self.course.slug, assignment_id, submission_response.data["id"]],
            ),
            format="json",
        )
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data["status"], "retrieved")
        self.assertIsNone(retrieve_response.data["reviewed_at"])
        self.assertEqual(retrieve_response.data["score"], 9)
        self.assertEqual(
            retrieve_response.data["feedback"],
            "Good work. Improve the mobile navigation.",
        )

        self.client.force_authenticate(self.student)
        student_edit_while_retrieved_response = self.client.post(
            reverse("student-homework-submission", args=[assignment_id]),
            {"content": "Trying to edit while the teacher is revising the review."},
            format="json",
        )
        self.assertEqual(
            student_edit_while_retrieved_response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.client.force_authenticate(self.teacher)
        second_review_response = self.client.patch(
            reverse(
                "homework-submission-review",
                args=[self.course.slug, assignment_id, submission_response.data["id"]],
            ),
            {"score": 10, "feedback": "Excellent after a second look."},
            format="json",
        )
        self.assertEqual(second_review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_review_response.data["status"], "reviewed")
        self.assertEqual(second_review_response.data["score"], 10)
        self.assertEqual(second_review_response.data["feedback"], "Excellent after a second look.")

    def test_test_homework_submit_requires_a_completed_attempt(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Required quiz",
            passing_score=80,
            order=1,
        )
        Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.TRUE_FALSE,
            text="Complete this quiz.",
            correct_bool=True,
            order=1,
        )
        assignment = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            lesson=lesson,
            test=test,
            created_by=self.teacher,
            title="Quiz homework",
            description="",
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
            published_at=timezone.now(),
        )
        HomeworkAssignmentRecipient.objects.create(
            assignment=assignment,
            enrollment=self.student_enrollment,
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("student-homework-submission", args=[assignment.id]),
            {"content": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Complete the test", response.data["detail"])

    def test_student_homework_test_detail_hides_answer_key(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Hidden answers quiz",
            passing_score=80,
            order=1,
        )
        Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.TRUE_FALSE,
            text="Students should not receive this answer.",
            correct_bool=True,
            order=1,
        )
        assignment = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            lesson=lesson,
            test=test,
            created_by=self.teacher,
            title="Quiz homework",
            description="",
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
            published_at=timezone.now(),
        )
        HomeworkAssignmentRecipient.objects.create(
            assignment=assignment,
            enrollment=self.student_enrollment,
        )
        self.client.force_authenticate(self.student)

        response = self.client.get(reverse("student-homework-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question_payload = response.data[0]["test_detail"]["questions"][0]
        self.assertNotIn("correct_bool", question_payload)
        self.assertNotIn("correct_indices", question_payload)
        self.assertNotIn("sample_answer", question_payload)

    def test_test_homework_submit_sends_best_test_attempt_to_teacher(self):
        lesson = Lesson.objects.create(module=self.module, title="Lesson 1", order=1)
        test = Test.objects.create(
            module=self.module,
            title="Best attempt quiz",
            passing_score=80,
            order=1,
        )
        question = Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.TRUE_FALSE,
            text="The best attempt should be sent.",
            correct_bool=True,
            order=1,
        )
        assignment = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            lesson=lesson,
            test=test,
            created_by=self.teacher,
            title="Quiz homework",
            description="",
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
            published_at=timezone.now(),
        )
        HomeworkAssignmentRecipient.objects.create(
            assignment=assignment,
            enrollment=self.student_enrollment,
        )
        weak_attempt = TestAttempt.objects.create(
            student_profile=self.student_profile,
            test=test,
            attempt_number=1,
            score=0,
            passed=False,
            answers=[{"question_id": question.id, "answer_bool": False}],
        )
        best_attempt = TestAttempt.objects.create(
            student_profile=self.student_profile,
            test=test,
            attempt_number=2,
            score=100,
            passed=True,
            answers=[{"question_id": question.id, "answer_bool": True}],
        )
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("student-homework-submission", args=[assignment.id]),
            {"content": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["test_attempt"]["attempt_id"], best_attempt.id)
        self.assertNotEqual(response.data["test_attempt"]["attempt_id"], weak_attempt.id)
        submission = HomeworkSubmission.objects.get(assignment=assignment)
        self.assertEqual(submission.best_test_attempt, best_attempt)

        self.client.force_authenticate(self.teacher)
        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        teacher_submission = list_response.data[0]["teacher_submissions"][0]
        self.assertEqual(teacher_submission["test_attempt"]["attempt_id"], best_attempt.id)

    def test_only_homework_sender_can_review_submission(self):
        sending_teacher, _ = make_teacher(email="sender@example.com")
        assignment = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            created_by=sending_teacher,
            title="Sent by another teacher",
            description="Review is scoped to the sender.",
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
            published_at=timezone.now(),
        )
        HomeworkAssignmentRecipient.objects.create(
            assignment=assignment,
            enrollment=self.student_enrollment,
        )
        submission = HomeworkSubmission.objects.create(
            assignment=assignment,
            enrollment=self.student_enrollment,
            content="Submitted answer",
        )

        self.client.force_authenticate(self.teacher)
        owner_response = self.client.patch(
            reverse(
                "homework-submission-review",
                args=[self.course.slug, assignment.id, submission.id],
            ),
            {"score": 8, "feedback": "Course owner is not the sender."},
            format="json",
        )
        self.assertEqual(owner_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(sending_teacher)
        sender_response = self.client.patch(
            reverse(
                "homework-submission-review",
                args=[self.course.slug, assignment.id, submission.id],
            ),
            {"score": 9, "feedback": "Reviewed by the sender."},
            format="json",
        )
        self.assertEqual(sender_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sender_response.data["status"], "reviewed")

    def test_teacher_can_publish_homework_to_cohort(self):
        delivery_format = CourseDeliveryFormat.objects.create(
            course=self.course,
            format_type=CourseDeliveryFormat.FormatType.GROUP,
        )
        self.student_enrollment.delivery_format = delivery_format
        self.student_enrollment.save(update_fields=["delivery_format"])
        cohort = Cohort.objects.create(
            course=self.course,
            delivery_format=delivery_format,
            name="Group A",
        )
        CohortMember.objects.create(cohort=cohort, enrollment=self.student_enrollment)
        self.client.force_authenticate(self.teacher)
        create_response = self.client.post(
            self.url,
            {
                "module": self.module.id,
                "title": "Group task",
                "description": "Submit the group exercise.",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        publish_response = self.client.post(
            reverse("homework-assignment-publish", args=[self.course.slug, create_response.data["id"]]),
            {"cohort_ids": [cohort.id]},
            format="json",
        )

        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(publish_response.data["recipients"]), 1)
        self.assertEqual(
            publish_response.data["recipients"][0]["enrollment_id"],
            self.student_enrollment.id,
        )
