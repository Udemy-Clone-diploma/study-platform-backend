from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import (
    ChatModerationAction,
    ChatUserRestriction,
    MessageReport,
)
from apps.chat.serializers import (
    ChatModerationActionSerializer,
    ChatModerationRequestSerializer,
)
from apps.chat.services import ChatService
from apps.notifications.services import NotificationService
from apps.users.models import User


@extend_schema(tags=["Chat"])
class ModeratorChatUserActionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_target(self, user_id: int):
        return get_object_or_404(User, pk=user_id)

    def check_moderator(self, request):
        if request.user.role != User.RoleChoices.MODERATOR:
            raise PermissionDenied("Only moderators can manage chat access.")

    def response_data(self, request, target):
        restriction = ChatUserRestriction.objects.filter(user=target).first()
        actions = ChatModerationAction.objects.filter(
            target_user=target,
        ).select_related("moderator", "report")[:100]
        warning_states = {}
        warning_actions = (
            ChatModerationAction.objects.filter(
                target_user=target,
                report__isnull=False,
                action__in=[
                    ChatModerationAction.ActionChoices.WARNING,
                    ChatModerationAction.ActionChoices.RETRACT_WARNING,
                ],
            )
            .values_list("report_id", "action")
            .order_by("-created_at", "-id")
        )
        for report_id, warning_action in warning_actions:
            warning_states.setdefault(report_id, warning_action)
        return {
            "user_id": target.pk,
            "is_restricted": bool(restriction and restriction.is_active),
            "restriction_reason": (
                restriction.reason if restriction and restriction.is_active else ""
            ),
            "restricted_at": (
                restriction.restricted_at if restriction and restriction.is_active else None
            ),
            "active_warning_report_ids": [
                report_id
                for report_id, warning_action in warning_states.items()
                if warning_action == ChatModerationAction.ActionChoices.WARNING
            ],
            "actions": ChatModerationActionSerializer(
                actions,
                many=True,
                context={"request": request},
            ).data,
        }

    def get(self, request, user_id: int):
        self.check_moderator(request)
        target = self.get_target(user_id)
        return Response(self.response_data(request, target))

    def post(self, request, user_id: int):
        self.check_moderator(request)
        target = self.get_target(user_id)
        if target.pk == request.user.pk or target.role in {
            User.RoleChoices.MODERATOR,
            User.RoleChoices.ADMINISTRATOR,
        }:
            raise ValidationError("This user cannot receive chat moderation actions.")

        serializer = ChatModerationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        note = serializer.validated_data.get("note", "").strip()
        report_id = serializer.validated_data.get("report_id")
        report = None
        if report_id:
            report = get_object_or_404(
                MessageReport.objects.select_related("message"),
                pk=report_id,
            )
            if report.message.sender_id != target.pk:
                raise ValidationError("The selected report does not belong to this user.")
        if (
            action
            in {
                ChatModerationAction.ActionChoices.WARNING,
                ChatModerationAction.ActionChoices.RETRACT_WARNING,
            }
            and report is None
        ):
            raise ValidationError("A report is required for warning actions.")

        official_chat = None
        official_participant = None
        official_participant_created = False
        official_message = None
        with transaction.atomic():
            restriction = (
                ChatUserRestriction.objects.select_for_update().filter(user=target).first()
            )
            if action == ChatModerationAction.ActionChoices.RESTRICT:
                if restriction and restriction.is_active:
                    raise ValidationError("This user is already restricted from writing in chats.")
                if restriction:
                    restriction.is_active = True
                    restriction.restricted_by = request.user
                    restriction.reason = note
                    restriction.restricted_at = timezone.now()
                    restriction.lifted_at = None
                    restriction.save(
                        update_fields=[
                            "is_active",
                            "restricted_by",
                            "reason",
                            "restricted_at",
                            "lifted_at",
                        ]
                    )
                else:
                    ChatUserRestriction.objects.create(
                        user=target,
                        restricted_by=request.user,
                        reason=note,
                    )
                title = "Chat access restricted"
                body = note or "A moderator has restricted your ability to write in chats."
            elif action == ChatModerationAction.ActionChoices.RESTORE:
                if not restriction or not restriction.is_active:
                    raise ValidationError("This user's chat access is not restricted.")
                restriction.is_active = False
                restriction.lifted_at = timezone.now()
                restriction.save(update_fields=["is_active", "lifted_at"])
                title = "Chat access restored"
                body = note or "A moderator has restored your ability to write in chats."
            elif action == ChatModerationAction.ActionChoices.WARNING:
                latest_warning_action = (
                    ChatModerationAction.objects.filter(
                        target_user=target,
                        report=report,
                        action__in=[
                            ChatModerationAction.ActionChoices.WARNING,
                            ChatModerationAction.ActionChoices.RETRACT_WARNING,
                        ],
                    )
                    .order_by("-created_at", "-id")
                    .first()
                )
                if (
                    latest_warning_action
                    and latest_warning_action.action == ChatModerationAction.ActionChoices.WARNING
                ):
                    raise ValidationError("A warning is already active for this report.")
                title = "Moderator warning"
                body = note or "A moderator has issued a warning about your chat activity."
            else:
                latest_warning_action = (
                    ChatModerationAction.objects.filter(
                        target_user=target,
                        report=report,
                        action__in=[
                            ChatModerationAction.ActionChoices.WARNING,
                            ChatModerationAction.ActionChoices.RETRACT_WARNING,
                        ],
                    )
                    .order_by("-created_at", "-id")
                    .first()
                )
                if (
                    not latest_warning_action
                    or latest_warning_action.action != ChatModerationAction.ActionChoices.WARNING
                ):
                    raise ValidationError("There is no active warning for this report.")
                title = "Moderator warning retracted"
                body = note or "A moderator has retracted the warning about your chat activity."

            ChatModerationAction.objects.create(
                target_user=target,
                moderator=request.user,
                report=report,
                action=action,
                note=note,
            )
            if action == ChatModerationAction.ActionChoices.WARNING:
                (
                    official_chat,
                    official_participant,
                    official_participant_created,
                    official_message,
                ) = ChatService.create_official_warning_message(
                    target,
                    report,
                    note,
                )
            NotificationService.send_email_only(
                recipient=target,
                title=title,
                body=body,
                link_url=f"/{target.role}-dashboard/chats",
            )

        if official_participant_created and official_chat and official_participant:
            events.broadcast_participant_added(
                official_chat,
                official_participant,
            )
        if official_message:
            events.broadcast_message_created(official_message)

        return Response(
            self.response_data(request, target),
            status=status.HTTP_201_CREATED,
        )
