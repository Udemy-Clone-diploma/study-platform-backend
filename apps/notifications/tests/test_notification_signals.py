from django.core import mail
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.notifications.models import Notification, NotificationPreference


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
        # The fan-out is enqueued via transaction.on_commit; capture so it runs
        # under APITestCase's rolled-back transaction.
        with self.captureOnCommitCallbacks(execute=True):
            lesson = Lesson.objects.create(module=self.module, title=title, order=1)
        return lesson

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
