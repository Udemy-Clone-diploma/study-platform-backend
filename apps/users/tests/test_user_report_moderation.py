from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatParticipant, ChatRoom, Message
from apps.notifications.models import Notification, NotificationPreference
from apps.users.models import User, UserReport, UserReportAction
from apps.users.services import UserReportService
from apps.users.tests._factories import make_user


@override_settings(ALLOWED_HOSTS=["testserver"])
class UserReportModerationTests(APITestCase):
    def setUp(self):
        self.reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="reporter@example.com",
            first_name="Report",
            last_name="Author",
        )
        self.target = make_user(
            role=User.RoleChoices.TEACHER,
            email="reported@example.com",
            first_name="Reported",
            last_name="Teacher",
        )
        self.moderator = make_user(
            role=User.RoleChoices.MODERATOR,
            email="moderator@example.com",
            first_name="Case",
            last_name="Moderator",
        )
        self.other_moderator = make_user(
            role=User.RoleChoices.MODERATOR,
            email="other-moderator@example.com",
        )
        self.admin = make_user(
            role=User.RoleChoices.ADMINISTRATOR,
            email="admin@example.com",
        )

    def _create_report(self, reporter=None, target=None, **overrides):
        return UserReportService.create_report(
            reporter or self.reporter,
            target or self.target,
            reason=overrides.get("reason", UserReport.ReasonChoices.HARASSMENT),
            details=overrides.get("details", "Private evidence from reporter"),
        )

    def _claim(self, report, moderator=None):
        self.client.force_authenticate(moderator or self.moderator)
        return self.client.post(
            reverse("user-report-moderation-claim", args=[report.pk]),
            {},
            format="json",
        )

    def _moderator_action(self, report, action, moderator=None, note=None):
        self.client.force_authenticate(moderator or self.moderator)
        return self.client.post(
            reverse("user-report-moderator-action", args=[report.pk]),
            {
                "action": action,
                "note": note or "A sufficiently detailed moderation decision.",
            },
            format="json",
        )

    def _admin_action(self, report, action, admin=None, note=None):
        self.client.force_authenticate(admin or self.admin)
        return self.client.post(
            reverse("user-report-admin-action", args=[report.pk]),
            {
                "action": action,
                "note": note or "A sufficiently detailed administrator decision.",
            },
            format="json",
        )

    def test_create_snapshot_active_duplicate_and_new_report_after_resolution(self):
        self.client.force_authenticate(self.reporter)
        url = reverse("user-report", args=[self.target.pk])

        first = self.client.post(
            url,
            {"reason": "spam", "details": "Repeated unsolicited advertising"},
            format="json",
        )
        duplicate = self.client.post(
            url,
            {"reason": "fraud", "details": "Another active complaint"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        report = UserReport.objects.get()
        self.assertEqual(report.status, UserReport.StatusChoices.PENDING)
        self.assertEqual(report.profile_snapshot["id"], self.target.pk)
        self.assertEqual(report.profile_snapshot["first_name"], "Reported")
        self.assertNotIn("email", report.profile_snapshot)

        self.assertEqual(self._claim(report).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._moderator_action(report, "dismiss").status_code,
            status.HTTP_200_OK,
        )

        self.client.force_authenticate(self.reporter)
        reopened = self.client.post(
            url,
            {"reason": "fraud", "details": "New evidence after resolution"},
            format="json",
        )
        self.assertEqual(reopened.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserReport.objects.count(), 2)

    def test_unassigned_queue_permissions_filters_and_self_exclusion(self):
        visible = self._create_report(reason=UserReport.ReasonChoices.SPAM)
        hidden = self._create_report(
            reporter=self.moderator,
            target=make_user(
                role=User.RoleChoices.STUDENT,
                email="moderator-target@example.com",
            ),
            reason=UserReport.ReasonChoices.SPAM,
        )

        self.client.force_authenticate(self.reporter)
        denied = self.client.get(reverse("user-report-moderation-unassigned"))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.moderator)
        response = self.client.get(
            reverse("user-report-moderation-unassigned"),
            {"reason": "spam", "search": "Reported"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], visible.pk)
        self.assertNotEqual(response.data["results"][0]["id"], hidden.pk)
        self.assertEqual(
            response.data["results"][0]["reported_user"]["name"],
            "Reported Teacher",
        )
        self.assertEqual(
            response.data["results"][0]["reported_user"]["status"],
            User.StatusChoices.ACTIVE,
        )
        self.assertEqual(
            response.data["results"][0]["reported_user"]["email"],
            self.target.email,
        )
        self.assertIsNotNone(
            response.data["results"][0]["reported_user"]["date_joined"]
        )

    def test_claim_is_atomic_idempotent_and_creates_missing_profile(self):
        report = self._create_report()

        first = self._claim(report)
        retry = self._claim(report)
        conflict = self._claim(report, self.other_moderator)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(conflict.status_code, status.HTTP_409_CONFLICT)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.StatusChoices.IN_REVIEW)
        self.assertEqual(report.assigned_moderator.user_id, self.moderator.pk)
        self.assertEqual(
            report.actions.filter(action=UserReportAction.ActionChoices.CLAIMED).count(),
            1,
        )

    def test_unavailable_moderator_assignment_can_be_reclaimed(self):
        report = self._create_report()
        self.assertEqual(
            self._claim(report, self.other_moderator).status_code,
            status.HTTP_200_OK,
        )
        User.all_objects.filter(pk=self.other_moderator.pk).update(
            is_active=False,
        )

        self.client.force_authenticate(self.moderator)
        queue = self.client.get(reverse("user-report-moderation-unassigned"))
        self.assertEqual(queue.data["results"][0]["id"], report.pk)

        reclaimed = self._claim(report)
        self.assertEqual(reclaimed.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.StatusChoices.IN_REVIEW)
        self.assertEqual(report.assigned_moderator.user_id, self.moderator.pk)
        actions = report.actions.filter(action=UserReportAction.ActionChoices.CLAIMED)
        self.assertEqual(actions.count(), 2)
        self.assertEqual(
            actions.last().note,
            "Reassigned from an unavailable moderator.",
        )

    def test_warning_uses_official_chat_and_email_without_platform_notification(self):
        report = self._create_report()
        self._claim(report)
        NotificationPreference.objects.create(
            user=self.target,
            overrides={
                Notification.TypeChoices.MODERATION_ACTION: {
                    "in_app": False,
                    "email": False,
                }
            },
        )
        note = "The reviewed profile violates the platform conduct policy."

        with self.captureOnCommitCallbacks(execute=True):
            first = self._moderator_action(report, "warning", note=note)
        with self.captureOnCommitCallbacks(execute=True):
            retry = self._moderator_action(report, "warning", note=note)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.StatusChoices.RESOLVED)
        self.assertEqual(report.resolution, UserReport.ResolutionChoices.WARNING)
        self.assertEqual(
            report.actions.filter(action=UserReportAction.ActionChoices.WARNING).count(),
            1,
        )
        self.assertFalse(Notification.objects.filter(recipient=self.target).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(note, mail.outbox[0].body)

        official_chat = ChatRoom.objects.get(
            direct_key=f"school_admin_{self.target.pk}"
        )
        self.assertEqual(official_chat.title, "School Administration")
        self.assertTrue(official_chat.is_read_only)
        self.assertTrue(
            ChatParticipant.objects.filter(
                chat=official_chat,
                user=self.target,
                left_at__isnull=True,
            ).exists()
        )
        messages = Message.objects.filter(chat=official_chat)
        self.assertEqual(messages.count(), 1)
        warning_text = messages.get().text
        self.assertIn(note, warning_text)
        self.assertNotIn(self.reporter.email, warning_text)
        self.assertNotIn(report.details, warning_text)

    def test_moderator_block_resolves_pending_and_review_but_not_escalated(self):
        current = self._create_report()
        second_reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="second-reporter@example.com",
        )
        pending = self._create_report(reporter=second_reporter)
        escalated_reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="escalated-reporter@example.com",
        )
        escalated = UserReport.objects.create(
            reporter=escalated_reporter,
            reported_user=self.target,
            reason=UserReport.ReasonChoices.VIOLENCE,
            status=UserReport.StatusChoices.ESCALATED,
            escalated_at=timezone.now(),
        )
        self._claim(current)

        with self.captureOnCommitCallbacks(execute=True):
            response = self._moderator_action(current, "block")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        current.refresh_from_db()
        pending.refresh_from_db()
        escalated.refresh_from_db()
        self.assertTrue(self.target.is_blocked)
        self.assertEqual(current.resolution, UserReport.ResolutionChoices.BLOCKED)
        self.assertEqual(pending.resolution, UserReport.ResolutionChoices.BLOCKED)
        self.assertEqual(escalated.status, UserReport.StatusChoices.ESCALATED)
        self.assertEqual(current.actions.filter(action="blocked").count(), 1)
        self.assertEqual(pending.actions.filter(action="blocked").count(), 1)
        self.assertEqual(escalated.actions.filter(action="blocked").count(), 0)
        self.assertEqual(
            self._moderator_action(pending, "block").status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_moderator_can_reverse_own_block_and_history_is_updated(self):
        report = self._create_report()
        self._claim(report)

        with self.captureOnCommitCallbacks(execute=True):
            blocked = self._moderator_action(report, "block")
        with self.captureOnCommitCallbacks(execute=True):
            unblocked = self._moderator_action(
                report,
                "unblock",
                note="The original block decision was reversed after an appeal.",
            )

        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertEqual(unblocked.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_blocked)
        self.assertEqual(self.target.status, User.StatusChoices.ACTIVE)
        self.assertEqual(report.status, UserReport.StatusChoices.RESOLVED)
        self.assertEqual(report.resolution, UserReport.ResolutionChoices.UNBLOCKED)
        unblock_action = report.actions.get(
            action=UserReportAction.ActionChoices.UNBLOCKED
        )
        self.assertEqual(unblock_action.actor_id, self.moderator.pk)
        self.assertEqual(
            unblock_action.previous_status,
            UserReport.StatusChoices.RESOLVED,
        )
        self.assertEqual(unblock_action.new_status, UserReport.StatusChoices.RESOLVED)
        self.assertEqual(unblocked.data["resolution"], "unblocked")
        self.assertFalse(unblocked.data["reported_user"]["is_blocked"])
        self.assertEqual(unblocked.data["actions"][-1]["action"], "unblocked")
        self.assertFalse(Notification.objects.filter(recipient=self.target).exists())
        self.assertEqual(len(mail.outbox), 2)

        retry = self._moderator_action(report, "unblock")
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(
            report.actions.filter(action=UserReportAction.ActionChoices.UNBLOCKED).count(),
            1,
        )

    def test_admin_can_unblock_a_moderator_block(self):
        report = self._create_report()
        self._claim(report)
        self._moderator_action(report, "block")

        response = self._admin_action(
            report,
            "unblock",
            note="Administrator restored access after reviewing the user's appeal.",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_blocked)
        self.assertEqual(report.resolution, UserReport.ResolutionChoices.UNBLOCKED)
        self.assertEqual(
            list(report.actions.values_list("action", flat=True)),
            [
                UserReportAction.ActionChoices.CLAIMED,
                UserReportAction.ActionChoices.BLOCKED,
                UserReportAction.ActionChoices.UNBLOCKED,
            ],
        )
        self.assertEqual(response.data["actions"][-1]["actor"]["id"], self.admin.pk)

    def test_admin_all_queue_includes_unassigned_and_non_escalated_reports(self):
        pending = self._create_report()
        in_review = self._create_report(
            reporter=make_user(
                role=User.RoleChoices.STUDENT,
                email="all-in-review-reporter@example.com",
            )
        )
        self._claim(in_review)
        escalated = UserReport.objects.create(
            reporter=make_user(
                role=User.RoleChoices.STUDENT,
                email="all-escalated-reporter@example.com",
            ),
            reported_user=self.target,
            reason=UserReport.ReasonChoices.FRAUD,
            status=UserReport.StatusChoices.ESCALATED,
            escalated_at=timezone.now(),
        )
        resolved = UserReport.objects.create(
            reporter=make_user(
                role=User.RoleChoices.STUDENT,
                email="all-resolved-reporter@example.com",
            ),
            reported_user=self.target,
            reason=UserReport.ReasonChoices.SPAM,
            status=UserReport.StatusChoices.RESOLVED,
            resolution=UserReport.ResolutionChoices.DISMISSED,
        )
        self_related = UserReport.objects.create(
            reporter=self.admin,
            reported_user=self.target,
            reason=UserReport.ReasonChoices.OTHER,
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("user-report-moderation-all"))
        unassigned = self.client.get(reverse("user-report-moderation-unassigned"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in response.data["results"]},
            {pending.pk, in_review.pk, escalated.pk, resolved.pk, self_related.pk},
        )
        self.assertEqual(unassigned.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in unassigned.data["results"]},
            {pending.pk, self_related.pk},
        )

    def test_staff_report_auto_escalates_to_admin_only_without_sensitive_notification(self):
        staff_target = make_user(
            role=User.RoleChoices.MODERATOR,
            email="reported-staff@example.com",
        )
        second_admin = make_user(
            role=User.RoleChoices.ADMINISTRATOR,
            email="second-admin@example.com",
        )

        with self.captureOnCommitCallbacks(execute=True):
            report = self._create_report(
                target=staff_target,
                details="Highly sensitive reporter evidence",
            )

        self.assertEqual(report.status, UserReport.StatusChoices.ESCALATED)
        self.assertIsNotNone(report.escalated_at)
        action = report.actions.get()
        self.assertEqual(action.action, UserReportAction.ActionChoices.ESCALATED)
        self.assertIsNone(action.actor)
        self.assertEqual(action.actor_role, "system")
        recipients = set(
            Notification.objects.values_list("recipient_id", flat=True)
        )
        self.assertEqual(recipients, {self.admin.pk, second_admin.pk})
        for notification in Notification.objects.all():
            self.assertEqual(notification.link_url, "/admin/reports")
            self.assertNotIn(report.details, notification.body)
            self.assertNotIn(self.reporter.email, notification.body)

        self.client.force_authenticate(self.moderator)
        moderator_queue = self.client.get(reverse("user-report-moderation-unassigned"))
        self.assertNotIn(
            report.pk,
            [item["id"] for item in moderator_queue.data["results"]],
        )

        self.client.force_authenticate(self.admin)
        admin_queue = self.client.get(reverse("user-report-moderation-escalated"))
        self.assertEqual(admin_queue.data["results"][0]["id"], report.pk)

    def test_moderator_escalation_and_admin_dismiss_are_idempotent(self):
        report = self._create_report()
        self._claim(report)

        with self.captureOnCommitCallbacks(execute=True):
            escalation = self._moderator_action(report, "escalate")
        self.assertEqual(escalation.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.StatusChoices.ESCALATED)

        first = self._admin_action(report, "dismiss")
        retry = self._admin_action(report, "dismiss")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.StatusChoices.RESOLVED)
        self.assertEqual(report.resolution, UserReport.ResolutionChoices.DISMISSED)
        self.assertEqual(
            report.actions.filter(action=UserReportAction.ActionChoices.DISMISSED).count(),
            1,
        )

        self.client.force_authenticate(self.admin)
        active_queue = self.client.get(reverse("user-report-moderation-escalated"))
        history = self.client.get(
            reverse("user-report-moderation-escalated"),
            {"status": UserReport.StatusChoices.RESOLVED},
        )
        self.assertEqual(active_queue.data["count"], 0)
        self.assertEqual(history.data["results"][0]["id"], report.pk)

    def test_admin_block_resolves_all_active_reports_including_escalated(self):
        pending = self._create_report()
        second_reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="admin-block-second-reporter@example.com",
        )
        in_review = self._create_report(reporter=second_reporter)
        self._claim(in_review)
        escalated_reporter = make_user(
            role=User.RoleChoices.STUDENT,
            email="admin-block-escalated-reporter@example.com",
        )
        escalated = UserReport.objects.create(
            reporter=escalated_reporter,
            reported_user=self.target,
            reason=UserReport.ReasonChoices.FRAUD,
            status=UserReport.StatusChoices.ESCALATED,
            escalated_at=timezone.now(),
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self._admin_action(escalated, "block")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for report in (pending, in_review, escalated):
            report.refresh_from_db()
            self.assertEqual(report.status, UserReport.StatusChoices.RESOLVED)
            self.assertEqual(report.resolution, UserReport.ResolutionChoices.BLOCKED)
            self.assertEqual(report.actions.filter(action="blocked").count(), 1)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_blocked)
        self.assertEqual(
            self._admin_action(pending, "block").status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_admin_cannot_resolve_self_related_report_and_validates_note(self):
        report = UserReport.objects.create(
            reporter=self.admin,
            reported_user=self.target,
            reason=UserReport.ReasonChoices.OTHER,
            status=UserReport.StatusChoices.ESCALATED,
            escalated_at=timezone.now(),
        )

        self.assertEqual(
            self._admin_action(report, "dismiss").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get(reverse("user-report-moderation-escalated")).data[
                "count"
            ],
            0,
        )

        other_admin = make_user(
            role=User.RoleChoices.ADMINISTRATOR,
            email="valid-admin@example.com",
        )
        invalid = self._admin_action(
            report,
            "dismiss",
            admin=other_admin,
            note="short",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
