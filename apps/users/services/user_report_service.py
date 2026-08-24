from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.exceptions import (
    CannotReportSelfError,
    UserAlreadyReportedError,
    UserReportConflictError,
    UserReportNotFoundError,
    UserReportPermissionError,
)
from apps.users.models import User, UserReport, UserReportAction
from apps.users.serializers.PublicUserSerializer import PublicUserSerializer
from apps.users.services.user_service import UserService


class UserReportService:
    ACTIVE_STATUSES = (
        UserReport.StatusChoices.PENDING,
        UserReport.StatusChoices.IN_REVIEW,
        UserReport.StatusChoices.ESCALATED,
    )
    STAFF_ROLES = (
        User.RoleChoices.MODERATOR,
        User.RoleChoices.ADMINISTRATOR,
    )

    MODERATOR_ACTIONS = {
        "warning": UserReportAction.ActionChoices.WARNING,
        "block": UserReportAction.ActionChoices.BLOCKED,
        "unblock": UserReportAction.ActionChoices.UNBLOCKED,
        "escalate": UserReportAction.ActionChoices.ESCALATED,
        "dismiss": UserReportAction.ActionChoices.DISMISSED,
    }
    ADMIN_ACTIONS = {
        "warning": UserReportAction.ActionChoices.WARNING,
        "block": UserReportAction.ActionChoices.BLOCKED,
        "unblock": UserReportAction.ActionChoices.UNBLOCKED,
        "dismiss": UserReportAction.ActionChoices.DISMISSED,
    }

    @classmethod
    @transaction.atomic
    def create_report(
        cls,
        reporter: User,
        reported_user: User,
        *,
        reason: str,
        details: str = "",
    ) -> UserReport:
        if reporter.pk == reported_user.pk:
            raise CannotReportSelfError

        is_staff_report = reported_user.role in cls.STAFF_ROLES
        now = timezone.now()
        profile_snapshot = cls._build_profile_snapshot(reported_user)

        try:
            report = UserReport.objects.create(
                reported_user=reported_user,
                reporter=reporter,
                reason=reason,
                details=details,
                profile_snapshot=profile_snapshot,
                status=(
                    UserReport.StatusChoices.ESCALATED
                    if is_staff_report
                    else UserReport.StatusChoices.PENDING
                ),
                escalated_at=now if is_staff_report else None,
                escalation_note=(
                    "Automatically escalated because the reported account is staff."
                    if is_staff_report
                    else ""
                ),
            )
        except IntegrityError as exc:
            raise UserAlreadyReportedError from exc

        if is_staff_report:
            cls._record_action(
                report,
                actor=None,
                action=UserReportAction.ActionChoices.ESCALATED,
                previous_status=UserReport.StatusChoices.PENDING,
                new_status=UserReport.StatusChoices.ESCALATED,
                note=report.escalation_note,
            )
            cls._schedule_admin_escalation_notification(report)

        return report

    @classmethod
    def has_active_report(cls, reporter: User, reported_user: User) -> bool:
        return UserReport.objects.filter(
            reporter=reporter,
            reported_user=reported_user,
            status__in=cls.ACTIVE_STATUSES,
        ).exists()

    @classmethod
    def get_unassigned_queryset(cls, actor: User) -> QuerySet[UserReport]:
        queryset = cls._base_queryset().filter(
            Q(
                status=UserReport.StatusChoices.PENDING,
                assigned_moderator__isnull=True,
            )
            | (Q(status=UserReport.StatusChoices.IN_REVIEW) & cls._unavailable_assignment_query())
        )
        if actor.role == User.RoleChoices.MODERATOR:
            queryset = queryset.exclude(Q(reporter=actor) | Q(reported_user=actor))
        return queryset.order_by("created_at", "id")

    @classmethod
    def get_mine_queryset(cls, actor: User) -> QuerySet[UserReport]:
        moderator_profile = getattr(actor, "moderator_profile", None)
        if moderator_profile is None:
            return UserReport.objects.none()
        return (
            cls._base_queryset()
            .filter(assigned_moderator=moderator_profile)
            .order_by("-updated_at", "-id")
        )

    @classmethod
    def get_escalated_queryset(cls, actor: User) -> QuerySet[UserReport]:
        return (
            cls._base_queryset()
            .filter(escalated_at__isnull=False)
            .exclude(Q(reporter=actor) | Q(reported_user=actor))
            .order_by("-escalated_at", "-id")
        )

    @classmethod
    def get_all_queryset(cls) -> QuerySet[UserReport]:
        return cls._base_queryset().order_by("-updated_at", "-id")

    @classmethod
    @transaction.atomic
    def claim_report(cls, report_id: int, actor: User) -> UserReport:
        if actor.role != User.RoleChoices.MODERATOR:
            raise UserReportPermissionError("Only moderators can claim reports.")

        report = cls._get_locked_report(report_id)
        cls._ensure_not_self_related(report, actor)
        moderator_profile = UserService.ensure_profile(actor)

        if (
            report.status == UserReport.StatusChoices.IN_REVIEW
            and report.assigned_moderator_id == moderator_profile.id
            and report.actions.filter(
                actor=actor,
                action=UserReportAction.ActionChoices.CLAIMED,
            ).exists()
        ):
            return report

        is_pending = (
            report.status == UserReport.StatusChoices.PENDING
            and report.assigned_moderator_id is None
        )
        is_orphaned = (
            report.status == UserReport.StatusChoices.IN_REVIEW
            and cls._has_unavailable_assignment(report)
        )
        if not is_pending and not is_orphaned:
            raise UserReportConflictError("This report is no longer available to claim.")

        previous_status = report.status
        report.status = UserReport.StatusChoices.IN_REVIEW
        report.assigned_moderator = moderator_profile
        report.assigned_at = timezone.now()
        report.save(
            update_fields=[
                "status",
                "assigned_moderator",
                "assigned_at",
                "updated_at",
            ]
        )
        cls._record_action(
            report,
            actor=actor,
            action=UserReportAction.ActionChoices.CLAIMED,
            previous_status=previous_status,
            new_status=report.status,
            note=("Reassigned from an unavailable moderator." if is_orphaned else ""),
        )
        return report

    @classmethod
    @transaction.atomic
    def moderator_action(
        cls,
        report_id: int,
        actor: User,
        *,
        action: str,
        note: str,
    ) -> UserReport:
        if actor.role != User.RoleChoices.MODERATOR:
            raise UserReportPermissionError("Only moderators can use this report action.")

        audit_action = cls.MODERATOR_ACTIONS[action]
        locked_target = None
        if action in {"block", "unblock"}:
            report, locked_target = cls._get_report_with_target_lock(report_id)
        else:
            report = cls._get_locked_report(report_id)
        cls._ensure_not_self_related(report, actor)
        moderator_profile = UserService.ensure_profile(actor)

        if report.assigned_moderator_id != moderator_profile.id:
            raise UserReportConflictError("Only the assigned moderator can act on this report.")

        if cls._is_idempotent(report, actor, audit_action):
            return report

        if action == "unblock":
            if (
                report.status != UserReport.StatusChoices.RESOLVED
                or report.resolution != UserReport.ResolutionChoices.BLOCKED
                or report.resolved_by_id != actor.pk
            ):
                raise UserReportConflictError(
                    "Moderators can only reverse their own block decision."
                )
            if not locked_target.is_blocked:
                raise UserReportConflictError("This user is already unblocked.")
            report = cls._unblock_target_and_update_reports(
                report,
                actor,
                note,
                locked_target=locked_target,
            )
            cls._schedule_target_notification(report, "unblocked", note)
            return report

        if report.status != UserReport.StatusChoices.IN_REVIEW:
            raise UserReportConflictError(
                "Only the assigned moderator can act on a report in review."
            )

        if action != "escalate" and report.reported_user.role in cls.STAFF_ROLES:
            raise UserReportPermissionError(
                "Reports about staff must be resolved by an administrator."
            )

        if action == "warning":
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.WARNING,
                action=UserReportAction.ActionChoices.WARNING,
                note=note,
            )
            cls._schedule_target_notification(report, "warning", note)
        elif action == "block":
            report = cls._block_target_and_resolve_reports(
                report,
                actor,
                note,
                locked_target=locked_target,
            )
            cls._schedule_target_notification(report, "blocked", note)
        elif action == "escalate":
            cls._escalate_report(report, actor=actor, note=note)
        else:
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.DISMISSED,
                action=UserReportAction.ActionChoices.DISMISSED,
                note=note,
            )

        return report

    @classmethod
    @transaction.atomic
    def admin_action(
        cls,
        report_id: int,
        actor: User,
        *,
        action: str,
        note: str,
    ) -> UserReport:
        if actor.role != User.RoleChoices.ADMINISTRATOR:
            raise UserReportPermissionError("Only administrators can use this report action.")

        audit_action = cls.ADMIN_ACTIONS[action]
        locked_target = None
        if action in {"block", "unblock"}:
            report, locked_target = cls._get_report_with_target_lock(report_id)
        else:
            report = cls._get_locked_report(report_id)
        cls._ensure_not_self_related(report, actor)

        if action == "unblock":
            if cls._is_idempotent(report, actor, audit_action):
                return report
            if (
                report.status != UserReport.StatusChoices.RESOLVED
                or report.resolution != UserReport.ResolutionChoices.BLOCKED
            ):
                raise UserReportConflictError(
                    "Administrators can only unblock from a blocked report."
                )
            if not locked_target.is_blocked:
                raise UserReportConflictError("This user is already unblocked.")
            report = cls._unblock_target_and_update_reports(
                report,
                actor,
                note,
                locked_target=locked_target,
            )
            cls._schedule_target_notification(report, "unblocked", note)
            return report

        if report.escalated_at is None:
            raise UserReportConflictError(
                "Administrators can only act on reports from the escalated queue."
            )

        if cls._is_idempotent(report, actor, audit_action):
            return report

        if report.status != UserReport.StatusChoices.ESCALATED:
            raise UserReportConflictError("Administrators can only act on escalated reports.")

        if action == "warning":
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.WARNING,
                action=UserReportAction.ActionChoices.WARNING,
                note=note,
            )
            cls._schedule_target_notification(report, "warning", note)
        elif action == "block":
            report = cls._block_target_and_resolve_reports(
                report,
                actor,
                note,
                locked_target=locked_target,
            )
            cls._schedule_target_notification(report, "blocked", note)
        else:
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.DISMISSED,
                action=UserReportAction.ActionChoices.DISMISSED,
                note=note,
            )

        return report

    @classmethod
    def _base_queryset(cls) -> QuerySet[UserReport]:
        return UserReport.objects.select_related(
            "reporter",
            "reported_user",
            "assigned_moderator__user",
            "escalated_by",
            "resolved_by",
        ).prefetch_related("actions__actor")

    @classmethod
    def _get_locked_report(cls, report_id: int) -> UserReport:
        try:
            return UserReport.objects.select_for_update().get(pk=report_id)
        except UserReport.DoesNotExist as exc:
            raise UserReportNotFoundError from exc

    @staticmethod
    def _unavailable_assignment_query() -> Q:
        return (
            Q(assigned_moderator__isnull=True)
            | Q(assigned_moderator__user__is_active=False)
            | Q(assigned_moderator__user__is_blocked=True)
            | Q(assigned_moderator__user__is_deleted=True)
            | Q(assigned_moderator__user__status=User.StatusChoices.INACTIVE)
            | ~Q(assigned_moderator__user__role=User.RoleChoices.MODERATOR)
        )

    @staticmethod
    def _has_unavailable_assignment(report: UserReport) -> bool:
        if report.assigned_moderator_id is None:
            return True
        assigned_user = report.assigned_moderator.user
        return bool(
            not assigned_user.is_active
            or assigned_user.is_blocked
            or assigned_user.is_deleted
            or assigned_user.status == User.StatusChoices.INACTIVE
            or assigned_user.role != User.RoleChoices.MODERATOR
        )

    @classmethod
    def _get_report_with_target_lock(
        cls,
        report_id: int,
    ) -> tuple[UserReport, User]:
        reported_user_id = (
            UserReport.objects.filter(pk=report_id)
            .values_list("reported_user_id", flat=True)
            .first()
        )
        if reported_user_id is None:
            raise UserReportNotFoundError
        try:
            target = User.all_objects.select_for_update().get(pk=reported_user_id)
        except User.DoesNotExist as exc:
            raise UserReportNotFoundError from exc
        return cls._get_locked_report(report_id), target

    @staticmethod
    def _build_profile_snapshot(user: User) -> dict:
        snapshot = dict(PublicUserSerializer(user).data)
        snapshot.pop("email", None)
        snapshot.pop("is_self", None)
        snapshot.pop("has_reported", None)
        return snapshot

    @staticmethod
    def _ensure_not_self_related(report: UserReport, actor: User) -> None:
        if actor.pk in {report.reporter_id, report.reported_user_id}:
            raise UserReportPermissionError(
                "You cannot process a report involving your own account."
            )

    @classmethod
    def _is_idempotent(
        cls,
        report: UserReport,
        actor: User,
        action: str,
    ) -> bool:
        if not report.actions.filter(actor=actor, action=action).exists():
            return False
        if action == UserReportAction.ActionChoices.ESCALATED:
            return report.status == UserReport.StatusChoices.ESCALATED
        expected_resolution = {
            UserReportAction.ActionChoices.WARNING: UserReport.ResolutionChoices.WARNING,
            UserReportAction.ActionChoices.BLOCKED: UserReport.ResolutionChoices.BLOCKED,
            UserReportAction.ActionChoices.UNBLOCKED: UserReport.ResolutionChoices.UNBLOCKED,
            UserReportAction.ActionChoices.DISMISSED: UserReport.ResolutionChoices.DISMISSED,
        }.get(action)
        return bool(
            expected_resolution
            and report.status == UserReport.StatusChoices.RESOLVED
            and report.resolution == expected_resolution
        )

    @classmethod
    def _resolve_report(
        cls,
        report: UserReport,
        *,
        actor: User,
        resolution: str,
        action: str,
        note: str,
    ) -> None:
        previous_status = report.status
        report.status = UserReport.StatusChoices.RESOLVED
        report.resolution = resolution
        report.resolved_by = actor
        report.resolved_at = timezone.now()
        report.resolution_note = note
        report.save(
            update_fields=[
                "status",
                "resolution",
                "resolved_by",
                "resolved_at",
                "resolution_note",
                "updated_at",
            ]
        )
        cls._record_action(
            report,
            actor=actor,
            action=action,
            previous_status=previous_status,
            new_status=report.status,
            note=note,
        )

    @classmethod
    def _escalate_report(cls, report: UserReport, *, actor: User, note: str) -> None:
        previous_status = report.status
        report.status = UserReport.StatusChoices.ESCALATED
        report.escalated_by = actor
        report.escalated_at = timezone.now()
        report.escalation_note = note
        report.save(
            update_fields=[
                "status",
                "escalated_by",
                "escalated_at",
                "escalation_note",
                "updated_at",
            ]
        )
        cls._record_action(
            report,
            actor=actor,
            action=UserReportAction.ActionChoices.ESCALATED,
            previous_status=previous_status,
            new_status=report.status,
            note=note,
        )
        cls._schedule_admin_escalation_notification(report)

    @classmethod
    def _block_target_and_resolve_reports(
        cls,
        current_report: UserReport,
        actor: User,
        note: str,
        *,
        locked_target: User,
    ) -> UserReport:
        UserService.set_block_status(locked_target, True, acting_user=actor)

        statuses = [
            UserReport.StatusChoices.PENDING,
            UserReport.StatusChoices.IN_REVIEW,
        ]
        if actor.role == User.RoleChoices.ADMINISTRATOR:
            statuses.append(UserReport.StatusChoices.ESCALATED)

        reports = list(
            UserReport.objects.select_for_update()
            .filter(reported_user_id=locked_target.pk, status__in=statuses)
            .order_by("id")
        )
        for report in reports:
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.BLOCKED,
                action=UserReportAction.ActionChoices.BLOCKED,
                note=note,
            )
            if report.pk == current_report.pk:
                current_report = report

        return current_report

    @classmethod
    def _unblock_target_and_update_reports(
        cls,
        current_report: UserReport,
        actor: User,
        note: str,
        *,
        locked_target: User,
    ) -> UserReport:
        UserService.set_block_status(locked_target, False, acting_user=actor)

        reports = list(
            UserReport.objects.select_for_update()
            .filter(
                reported_user_id=locked_target.pk,
                status=UserReport.StatusChoices.RESOLVED,
                resolution=UserReport.ResolutionChoices.BLOCKED,
            )
            .order_by("id")
        )
        for report in reports:
            cls._resolve_report(
                report,
                actor=actor,
                resolution=UserReport.ResolutionChoices.UNBLOCKED,
                action=UserReportAction.ActionChoices.UNBLOCKED,
                note=note,
            )
            if report.pk == current_report.pk:
                current_report = report

        return current_report

    @staticmethod
    def _record_action(
        report: UserReport,
        *,
        actor: User | None,
        action: str,
        previous_status: str,
        new_status: str,
        note: str = "",
    ) -> UserReportAction:
        return UserReportAction.objects.create(
            report=report,
            actor=actor,
            actor_role=actor.role if actor else "system",
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            note=note,
        )

    @classmethod
    def _schedule_admin_escalation_notification(cls, report: UserReport) -> None:
        admin_ids = list(
            User.objects.filter(
                role=User.RoleChoices.ADMINISTRATOR,
                status=User.StatusChoices.ACTIVE,
                is_active=True,
                is_blocked=False,
            )
            .exclude(pk__in=[report.reported_user_id, report.reporter_id])
            .values_list("id", flat=True)
        )
        report_id = report.pk

        def notify_admins():
            recipients = User.objects.filter(pk__in=admin_ids)
            NotificationService.fan_out(
                recipients=recipients,
                type=Notification.TypeChoices.MODERATION_ACTION,
                title="User report requires administrator review",
                body="An escalated user report is waiting for an administrator decision.",
                link_url="/admin/reports",
                payload={"report_id": report_id},
            )

        transaction.on_commit(notify_admins, robust=True)

    @staticmethod
    def _schedule_target_notification(
        report: UserReport,
        action: str,
        note: str,
    ) -> None:
        target_id = report.reported_user_id
        title = {
            "warning": "Account warning",
            "blocked": "Account access blocked",
            "unblocked": "Account access restored",
        }[action]
        body = note

        def notify_target():
            recipient = User.all_objects.filter(pk=target_id).first()
            if recipient is None:
                return
            NotificationService.send_email_only(
                recipient=recipient,
                title=title,
                body=body,
                link_url="/profile",
            )

            if action != "warning":
                return

            from apps.chat import events
            from apps.chat.services import ChatService

            with transaction.atomic():
                chat, participant, participant_created, message = (
                    ChatService.create_official_warning_message(
                        recipient,
                        report,
                        note,
                        warning_context="account",
                    )
                )
            if participant_created:
                events.broadcast_participant_added(chat, participant)
            events.broadcast_message_created(message)

        transaction.on_commit(notify_target, robust=True)
