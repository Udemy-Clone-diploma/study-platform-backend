from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatModerationAction, Message, MessageReport
from apps.chat.services import ChatService
from apps.courses.models import ApprovedCourseRecord
from apps.courses.tests._factories import make_course, make_teacher
from apps.reviews.models import Review, ReviewReport
from apps.users.models import User, UserReport, UserReportAction
from apps.users.services.user_service import UserService
from apps.users.tests._factories import make_user


class ModeratorDashboardTests(APITestCase):
    def setUp(self):
        self.moderator = make_user(
            role=User.RoleChoices.MODERATOR,
            email="dashboard-moderator@example.com",
            first_name="Morgan",
            last_name="Lee",
        )
        self.profile = UserService.ensure_profile(self.moderator)
        self.other_moderator = make_user(
            role=User.RoleChoices.MODERATOR,
            email="other-dashboard-moderator@example.com",
        )
        UserService.ensure_profile(self.other_moderator)
        self.admin = make_user(
            role=User.RoleChoices.ADMINISTRATOR,
            email="dashboard-admin@example.com",
        )
        self.reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="dashboard-reporter@example.com",
        )
        self.target = make_user(
            role=User.RoleChoices.TEACHER,
            email="dashboard-target@example.com",
        )

    def _report(self, *, status_value=UserReport.StatusChoices.RESOLVED):
        return UserReport.objects.create(
            reporter=self.reporter,
            reported_user=self.target,
            reason=UserReport.ReasonChoices.SPAM,
            status=status_value,
            assigned_moderator=self.profile,
        )

    def _action(self, action):
        report = self._report()
        return UserReportAction.objects.create(
            report=report,
            actor=self.moderator,
            actor_role=self.moderator.role,
            action=action,
            previous_status=UserReport.StatusChoices.IN_REVIEW,
            new_status=UserReport.StatusChoices.RESOLVED,
        )

    def test_dashboard_uses_real_moderator_actions_and_pending_work(self):
        self._action(UserReportAction.ActionChoices.WARNING)
        self._action(UserReportAction.ActionChoices.BLOCKED)
        previous_action = self._action(UserReportAction.ActionChoices.DISMISSED)
        UserReportAction.objects.filter(pk=previous_action.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        self._report(status_value=UserReport.StatusChoices.IN_REVIEW)

        self.client.force_authenticate(self.moderator)
        response = self.client.get(reverse("moderator-dashboard-statistics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["moderator"]["id"], self.moderator.pk)
        self.assertEqual(response.data["metrics"]["total_reviewed"]["value"], 2)
        self.assertEqual(
            response.data["metrics"]["harmful_content_blocked"]["value"],
            1,
        )
        self.assertEqual(response.data["metrics"]["pending_reviews"]["value"], 1)
        self.assertEqual(
            sum(row["reviewed"] for row in response.data["trends"]),
            2,
        )
        user_report_category = next(
            item
            for item in response.data["categories"]
            if item["key"] == "user_reports"
        )
        self.assertEqual(user_report_category["count"], 2)

    def test_admin_can_view_a_moderator_profile_but_moderators_cannot(self):
        url = reverse(
            "admin-moderator-dashboard-statistics",
            args=[self.moderator.pk],
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["moderator"]["email"], self.moderator.email)

        self.client.force_authenticate(self.other_moderator)
        forbidden = self.client.get(url)
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_combines_chat_course_and_review_moderation(self):
        teacher, teacher_profile = make_teacher(email="course-owner@example.com")
        course = make_course(teacher_profile, slug="dashboard-course")
        ApprovedCourseRecord.objects.create(
            course=course,
            teacher_profile=teacher_profile,
            moderator_profile=self.profile,
            course_slug=course.slug,
            course_title=course.title,
            course_level=course.level,
        )

        chat, _ = ChatService.create_direct_chat(self.reporter, self.target)
        message = Message.objects.create(
            chat=chat,
            sender=self.target,
            text="Reported chat content",
        )
        message_report = MessageReport.objects.create(
            message=message,
            reporter=self.reporter,
            reason=MessageReport.ReasonChoices.SPAM,
            message_text=message.text,
        )
        ChatModerationAction.objects.create(
            target_user=self.target,
            moderator=self.moderator,
            report=message_report,
            action=ChatModerationAction.ActionChoices.WARNING,
        )

        review = Review.objects.create(
            course=course,
            student=self.reporter,
            rating=2,
            text="Reported review",
            moderator_profile=self.profile,
            moderation_status=Review.ModerationStatusChoices.APPROVED,
            moderated_at=timezone.now(),
        )
        ReviewReport.objects.create(
            review=review,
            reporter=teacher,
            reason="Incorrect information",
        )
        second_reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="second-review-reporter@example.com",
        )
        ReviewReport.objects.create(
            review=review,
            reporter=second_reporter,
            reason="Misleading content",
        )

        self.client.force_authenticate(self.moderator)
        response = self.client.get(reverse("moderator-dashboard-statistics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"]["total_reviewed"]["value"], 3)
        category_counts = {
            item["key"]: item["count"] for item in response.data["categories"]
        }
        self.assertEqual(category_counts["chat_reports"], 1)
        self.assertEqual(category_counts["course_reviews"], 1)
        self.assertEqual(category_counts["reported_reviews"], 1)

    def test_admin_only_endpoint_rejects_non_moderator_target(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse(
                "admin-moderator-dashboard-statistics",
                args=[self.target.pk],
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
