from django.core import mail
from rest_framework.test import APITestCase

from apps.chat.models import ChatParticipant
from apps.chat.services import ChatService
from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
)
from apps.notifications.models import Notification, NotificationPreference
from apps.users.tests._factories import make_user


class LessonCreatedSignalTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher(email="sig_teacher@example.com")
        self.course = make_course(
            self.teacher_profile,
            slug="sig-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.module = Module.objects.create(course=self.course, title="M", order=1)

        self.s1_user, self.s1 = make_student(email="sig_s1@example.com")
        self.s2_user, self.s2 = make_student(email="sig_s2@example.com")
        self.revoked_user, self.revoked = make_student(email="sig_rev@example.com")

        Enrollment.objects.create(student_profile=self.s1, course=self.course)
        Enrollment.objects.create(student_profile=self.s2, course=self.course)
        Enrollment.objects.create(
            student_profile=self.revoked,
            course=self.course,
            access_status=Enrollment.AccessStatusChoices.REVOKED,
        )

    def _add_lesson(self, title="New Lesson"):
        return Lesson.objects.create(module=self.module, title=title, order=1)

    def test_fans_out_to_active_students_only(self):
        self._add_lesson()

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.s1_user.id, self.s2_user.id})
        # Revoked access and the teacher are excluded.
        self.assertNotIn(self.revoked_user.id, recipients)
        self.assertNotIn(self.teacher_profile.user_id, recipients)

    def test_notification_content(self):
        self._add_lesson(title="Closures")

        notification = Notification.objects.get(recipient=self.s1_user)
        self.assertEqual(notification.type, Notification.TypeChoices.NEW_LESSON)
        self.assertEqual(notification.title, self.course.title)
        self.assertIn("Closures", notification.body)
        self.assertEqual(notification.payload["course_slug"], self.course.slug)
        self.assertEqual(notification.payload["module_id"], self.module.id)

    def test_no_email_by_default(self):
        # new_lesson default: email False.
        self._add_lesson()
        self.assertEqual(len(mail.outbox), 0)

    def test_email_sent_when_student_opts_in(self):
        NotificationPreference.objects.create(
            user=self.s1_user, overrides={"new_lesson": {"email": True}}
        )

        self._add_lesson()

        self.assertEqual([message.to[0] for message in mail.outbox], [self.s1_user.email])

    def test_in_app_override_excludes_student(self):
        NotificationPreference.objects.create(
            user=self.s1_user, overrides={"new_lesson": {"in_app": False}}
        )

        self._add_lesson()

        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.s2_user.id})

    def test_draft_course_does_not_notify(self):
        draft = make_course(
            self.teacher_profile,
            title="Draft",
            slug="sig-draft",
            status=Course.StatusChoices.DRAFT,
        )
        draft_module = Module.objects.create(course=draft, title="M", order=1)
        Enrollment.objects.create(student_profile=self.s1, course=draft)

        Lesson.objects.create(module=draft_module, title="L", order=1)

        self.assertEqual(Notification.objects.count(), 0)

    def test_updating_lesson_does_not_refire(self):
        lesson = self._add_lesson()
        Notification.objects.all().delete()

        lesson.title = "Renamed"
        lesson.save()

        self.assertEqual(Notification.objects.count(), 0)


class ChatMessageCreatedSignalTests(APITestCase):
    def setUp(self):
        self.student = make_user(
            role="student",
            email="chat_signal_student@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.teacher = make_user(role="teacher", email="chat_signal_teacher@example.com")
        self.chat, _ = ChatService.create_direct_chat(self.student, self.teacher)

    def test_notifies_other_active_participant(self):
        message = ChatService.create_message(
            self.chat,
            self.student,
            text="Please check this message.",
        )

        notification = Notification.objects.get(recipient=self.teacher)
        self.assertEqual(notification.type, Notification.TypeChoices.NEW_MESSAGE)
        self.assertEqual(notification.actor, self.student)
        self.assertEqual(notification.link_url, "/teacher-dashboard/chats")
        self.assertEqual(notification.payload["chat_id"], self.chat.id)
        self.assertEqual(notification.payload["message_id"], message.id)
        self.assertIn("Ada Lovelace", notification.title)
        self.assertFalse(Notification.objects.filter(recipient=self.student).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_muted_participant_is_not_notified(self):
        ChatParticipant.objects.filter(chat=self.chat, user=self.teacher).update(is_muted=True)

        ChatService.create_message(self.chat, self.student, text="Muted message")

        self.assertEqual(Notification.objects.count(), 0)


class HomeworkSubmissionSignalTests(APITestCase):
    def setUp(self):
        self.teacher, teacher_profile = make_teacher(email="hw_notify_teacher@example.com")
        self.course = make_course(
            teacher_profile,
            slug="hw-notify-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.module = Module.objects.create(course=self.course, title="Module", order=1)
        self.student_user, self.student_profile = make_student(
            email="hw_notify_student@example.com"
        )
        self.enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.assignment = HomeworkAssignment.objects.create(
            course=self.course,
            module=self.module,
            created_by=self.teacher,
            title="Portfolio review",
            description="Submit your work.",
            status=HomeworkAssignment.StatusChoices.PUBLISHED,
        )
        HomeworkAssignmentRecipient.objects.create(
            assignment=self.assignment,
            enrollment=self.enrollment,
        )

    def test_submitted_homework_notifies_teacher(self):
        submission = HomeworkSubmission.objects.create(
            assignment=self.assignment,
            enrollment=self.enrollment,
            content="My solution",
        )

        notification = Notification.objects.get(recipient=self.teacher)
        self.assertEqual(notification.type, Notification.TypeChoices.HOMEWORK_SUBMITTED)
        self.assertEqual(notification.actor, self.student_user)
        self.assertEqual(notification.link_url, "/teacher-dashboard/homework")
        self.assertEqual(notification.payload["assignment_id"], self.assignment.id)
        self.assertEqual(notification.payload["submission_id"], submission.id)
        self.assertIn("Portfolio review", notification.body)
        self.assertEqual(len(mail.outbox), 1)

    def test_reviewed_homework_notifies_student(self):
        submission = HomeworkSubmission.objects.create(
            assignment=self.assignment,
            enrollment=self.enrollment,
            content="My solution",
        )
        Notification.objects.all().delete()
        mail.outbox.clear()

        submission.status = HomeworkSubmission.StatusChoices.REVIEWED
        submission.score = 5
        submission.feedback = "Good work."
        submission.save()

        notification = Notification.objects.get(recipient=self.student_user)
        self.assertEqual(notification.type, Notification.TypeChoices.HOMEWORK_GRADED)
        self.assertEqual(notification.actor, self.teacher)
        self.assertEqual(notification.title, "Homework returned")
        self.assertEqual(notification.link_url, "/student-dashboard/homework")
        self.assertEqual(notification.payload["score"], 5)
        self.assertEqual(len(mail.outbox), 1)

    def test_resaving_same_submitted_status_does_not_notify_again(self):
        submission = HomeworkSubmission.objects.create(
            assignment=self.assignment,
            enrollment=self.enrollment,
            content="My solution",
        )

        submission.content = "Edited text"
        submission.save(update_fields=["content", "updated_at"])

        self.assertEqual(Notification.objects.count(), 1)
