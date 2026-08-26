from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.enrollments.models import Enrollment
from apps.enrollments.services import EnrollmentService
from apps.enrollments.tests._factories import make_student


class EnrollmentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher(email="enrollments_teacher@example.com")
        cls.course = make_course(
            cls.teacher_profile,
            slug="enrollments-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        cls.student_user, cls.student_profile = make_student(
            email="enrollments_student@example.com"
        )

    def test_student_profile_courses_uses_enrollment_through_model(self):
        self.student_profile.courses.add(self.course)

        enrollment = Enrollment.objects.get(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.ACTIVE)
        self.assertIsNone(enrollment.order_id)
        self.assertIsNone(enrollment.access_until)

    def test_student_can_be_enrolled_in_course_once(self):
        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(
                    student_profile=self.student_profile,
                    course=self.course,
                )

    def test_access_check_honors_status_and_dates(self):
        access_granted_at = timezone.now() - timedelta(days=2)
        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
            access_granted_at=access_granted_at,
            access_until=access_granted_at + timedelta(days=1),
        )

        has_access = EnrollmentService.student_has_course_access(
            self.student_profile,
            self.course,
        )

        self.assertFalse(has_access)

    def test_suspend_blocks_content_access_but_stays_visible(self):
        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )

        enrollment.suspend()
        enrollment.refresh_from_db()

        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.SUSPENDED)
        self.assertFalse(
            EnrollmentService.student_has_course_access(self.student_profile, self.course)
        )
        self.assertIn(
            enrollment,
            Enrollment.objects.with_visible_access().filter(student_profile=self.student_profile),
        )
        self.assertNotIn(
            enrollment,
            Enrollment.objects.with_active_access().filter(student_profile=self.student_profile),
        )

    def test_get_access_status_reports_suspended_and_none(self):
        self.assertIsNone(EnrollmentService.get_access_status(self.student_user, self.course))

        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        enrollment.suspend()

        self.assertEqual(
            EnrollmentService.get_access_status(self.student_user, self.course),
            Enrollment.AccessStatusChoices.SUSPENDED,
        )
