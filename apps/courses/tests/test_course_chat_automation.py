from rest_framework.test import APITestCase

from apps.chat.models import ChatParticipant, ChatRoom
from apps.chat.services import ChatService
from apps.courses.models import Cohort, CohortMember, Course, CourseDeliveryFormat
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student

from ._factories import make_course, make_teacher


class CourseChatAutomationTests(APITestCase):
    def setUp(self):
        self.teacher, self.teacher_profile = make_teacher(
            email="course_chat_teacher@example.com"
        )
        self.course = make_course(
            self.teacher_profile,
            slug="course-chat-automation",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.student, self.student_profile = make_student(
            email="course_chat_student@example.com"
        )

    def test_cohort_creation_creates_teacher_owned_chat_and_members_join_it(self):
        cohort = Cohort.objects.create(
            course=self.course,
            name="Evening group",
            duration_months=3,
            hours_per_week=5,
        )

        chat = cohort.group_chat
        self.assertIsNotNone(chat)
        self.assertEqual(chat.type, ChatRoom.TypeChoices.GROUP)
        self.assertEqual(chat.created_by_id, self.teacher.id)
        self.assertTrue(
            ChatParticipant.objects.filter(
                chat=chat,
                user=self.teacher,
                role=ChatParticipant.RoleChoices.OWNER,
                left_at__isnull=True,
            ).exists()
        )

        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )
        CohortMember.objects.create(cohort=cohort, enrollment=enrollment)

        self.assertTrue(
            ChatParticipant.objects.filter(
                chat=chat,
                user=self.student,
                left_at__isnull=True,
            ).exists()
        )
        self.assertEqual(
            ChatParticipant.objects.filter(chat=chat, left_at__isnull=True).count(),
            2,
        )

    def test_enrollment_creates_one_reusable_direct_chat_with_course_teacher(self):
        enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )

        direct_key = ChatService.direct_key_for_users(self.teacher.id, self.student.id)
        chat = ChatRoom.objects.get(direct_key=direct_key)
        self.assertEqual(chat.type, ChatRoom.TypeChoices.DIRECT)
        self.assertEqual(chat.created_by_id, self.teacher.id)
        self.assertEqual(ChatParticipant.objects.filter(chat=chat).count(), 2)

        enrollment.save()
        self.assertEqual(ChatRoom.objects.filter(direct_key=direct_key).count(), 1)

    def test_self_paced_and_scheduled_formats_have_shared_chats(self):
        self_paced = CourseDeliveryFormat.objects.get(
            course=self.course,
            format_type=CourseDeliveryFormat.FormatType.SELF_PACED,
        )
        scheduled = CourseDeliveryFormat.objects.create(
            course=self.course,
            format_type=CourseDeliveryFormat.FormatType.SCHEDULED,
        )
        group = CourseDeliveryFormat.objects.create(
            course=self.course,
            format_type=CourseDeliveryFormat.FormatType.GROUP,
        )

        self.assertIsNotNone(self_paced.group_chat)
        self.assertIsNotNone(scheduled.group_chat)
        self.assertIsNone(group.group_chat_id)
        for delivery_format in (self_paced, scheduled):
            self.assertEqual(delivery_format.group_chat.created_by_id, self.teacher.id)
            self.assertTrue(
                ChatParticipant.objects.filter(
                    chat=delivery_format.group_chat,
                    user=self.teacher,
                    role=ChatParticipant.RoleChoices.OWNER,
                ).exists()
            )

        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
            delivery_format=self_paced,
        )

        self.assertTrue(
            ChatParticipant.objects.filter(
                chat=self_paced.group_chat,
                user=self.student,
                left_at__isnull=True,
            ).exists()
        )
        self.assertFalse(
            ChatParticipant.objects.filter(
                chat=scheduled.group_chat,
                user=self.student,
                left_at__isnull=True,
            ).exists()
        )
