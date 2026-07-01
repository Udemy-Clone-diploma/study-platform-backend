from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_pricing_plan, make_teacher
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.users.models import User


class EnrollmentApiTests(APITestCase):
    def setUp(self):
        self.teacher_user, self.teacher_profile = make_teacher(
            email="owner_enrollments@example.com"
        )
        _, self.other_teacher_profile = make_teacher(
            email="other_enrollments@example.com"
        )
        self.course = make_course(
            self.teacher_profile,
            title="Published Course",
            slug="published-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.other_course = make_course(
            self.other_teacher_profile,
            title="Other Course",
            slug="other-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.draft_course = make_course(
            self.teacher_profile,
            title="Draft Course",
            slug="draft-course",
            status=Course.StatusChoices.DRAFT,
        )
        self.student_user, self.student_profile = make_student(
            email="api_student@example.com"
        )
        _, self.other_student_profile = make_student(email="other_student@example.com")
        self.admin = User.objects.create_user(
            email="enrollments_admin@example.com",
            password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )

    def test_student_cannot_create_enrollment_without_payment(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("enrollments-list"),
            {
                "course_id": self.course.pk,
                "student_profile_id": self.other_student_profile.pk,
                "order_id": 123,
                "access_status": Enrollment.AccessStatusChoices.REVOKED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
            ).exists()
        )

    def test_student_cannot_enroll_in_draft_course(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("enrollments-list"),
            {"course_id": self.draft_course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_creates_enrollment_with_access_metadata(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("enrollments-list"),
            {
                "course_id": self.course.pk,
                "student_profile_id": self.student_profile.pk,
                "order_id": 456,
                "access_status": Enrollment.AccessStatusChoices.PENDING,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = Enrollment.objects.get(pk=response.data["id"])
        self.assertEqual(enrollment.student_profile, self.student_profile)
        self.assertEqual(enrollment.order_id, 456)
        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.PENDING)

    def test_student_enrolls_in_free_course(self):
        make_pricing_plan(self.course, price="0.00")
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("course-enroll-free", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = Enrollment.objects.get(pk=response.data["id"])
        self.assertEqual(enrollment.student_profile, self.student_profile)
        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.ACTIVE)
        self.assertIsNone(enrollment.order_id)

    def test_free_enrollment_rejects_paid_course(self):
        make_pricing_plan(self.course, price="10.00")
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("course-enroll-free", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
            ).exists()
        )

    def test_duplicate_enrollment_returns_validation_error(self):
        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("enrollments-list"),
            {"course_id": self.course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_lists_only_enrollments_for_owned_courses(self):
        owned = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.other_course,
        )
        self.client.force_authenticate(user=self.teacher_user)

        response = self.client.get(reverse("enrollments-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course_slugs = [row["course_slug"] for row in response.data["results"]]
        self.assertEqual(course_slugs, [owned.course.slug])

    def test_admin_updates_enrollment_status(self):
        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.students_count, 1)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("enrollments-detail", args=[enrollment.pk]),
            {"access_status": Enrollment.AccessStatusChoices.REVOKED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.REVOKED)
        self.course.refresh_from_db()
        self.assertEqual(self.course.students_count, 0)

    def test_delete_revokes_enrollment_instead_of_hard_deleting(self):
        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.delete(reverse("enrollments-detail", args=[enrollment.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.access_status, Enrollment.AccessStatusChoices.REVOKED)
        self.course.refresh_from_db()
        self.assertEqual(self.course.students_count, 0)
