from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import (
    ChatModerationAction,
    ChatParticipant,
    ChatRoom,
    ChatUserRestriction,
    Message,
    MessageAttachment,
    MessageReport,
)
from apps.chat.serializers import (
    ChatMessageAttachmentSerializer,
    ChatMessageSerializer,
    ChatModerationActionSerializer,
    ChatModerationRequestSerializer,
    ChatBlockSerializer,
    ChatMuteSerializer,
    ChatParticipantSerializer,
    ChatRoomSerializer,
    DirectChatCreateSerializer,
    GroupChatCreateSerializer,
    MessageAttachmentUploadSerializer,
    MessageCreateSerializer,
    MessageReportCreateSerializer,
    MessageReportSerializer,
    MessageUpdateSerializer,
    ParticipantAddSerializer,
    ParticipantRoleUpdateSerializer,
    ReadStatusSerializer,
)
from apps.chat.services import ChatService
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.models import User


def chat_queryset_for_user(user):
    return (
        ChatRoom.objects.filter(
            is_deleted=False,
            participants__user=user,
            participants__left_at__isnull=True,
        )
        .select_related("created_by", "last_message", "last_message__sender")
        .prefetch_related("participants__user")
        .distinct()
    )


def get_chat_for_user(user, chat_id: int) -> ChatRoom:
    return get_object_or_404(chat_queryset_for_user(user), pk=chat_id)


def message_queryset_for_user(user):
    return (
        Message.objects.filter(
            chat__is_deleted=False,
            chat__participants__user=user,
            chat__participants__left_at__isnull=True,
        )
        .select_related("chat", "sender", "reply_to")
        .prefetch_related("attachments")
        .distinct()
    )


@extend_schema(tags=["Chat"])
class ChatRoomViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return chat_queryset_for_user(self.request.user).order_by("-updated_at", "-id")

    def get_serializer_class(self):
        if self.action == "direct":
            return DirectChatCreateSerializer
        if self.action == "group":
            return GroupChatCreateSerializer
        if self.action == "mute":
            return ChatMuteSerializer
        if self.action == "block":
            return ChatBlockSerializer
        return ChatRoomSerializer

    @action(detail=False, methods=["post"], url_path="direct")
    def direct(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = serializer.save()
        response_status = status.HTTP_201_CREATED if serializer.created else status.HTTP_200_OK
        return Response(
            ChatRoomSerializer(chat, context=self.get_serializer_context()).data,
            status=response_status,
        )

    @action(detail=False, methods=["post"], url_path="group")
    def group(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat = serializer.save()
        return Response(
            ChatRoomSerializer(chat, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        chat = self.get_object()
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError("Only group chats can be updated.")
        if not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can update this chat.")
        serializer = self.get_serializer(chat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        events.broadcast_chat_updated(chat.pk)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="mute")
    def mute(self, request, pk=None):
        chat = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant = ChatService.set_mute(
            chat,
            request.user,
            is_muted=serializer.validated_data["is_muted"],
        )
        events.broadcast_chat_updated(chat.pk)
        return Response(
            ChatParticipantSerializer(participant, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        chat = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blocked_user, is_blocked = ChatService.set_direct_peer_block(
            chat,
            request.user,
            is_blocked=serializer.validated_data["is_blocked"],
        )
        events.broadcast_chat_updated(chat.pk)
        return Response(
            {
                "user_id": blocked_user.pk,
                "is_blocked": is_blocked,
            }
        )

    @action(detail=True, methods=["post"], url_path="clear-history")
    def clear_history(self, request, pk=None):
        chat = self.get_object()
        if chat.is_read_only:
            raise PermissionDenied("Official administration chats cannot be cleared.")
        ChatService.clear_history(chat, request.user)
        return Response(ChatRoomSerializer(chat, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        chat = self.get_object()
        if chat.is_read_only:
            raise PermissionDenied("Official administration chats cannot be deleted.")
        user_ids = ChatService.active_participant_user_ids(chat.pk)
        ChatService.delete_chat_for_everyone(chat)
        events.broadcast_chat_deleted(chat.pk, user_ids)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Chat"])
class ChatMessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_chat(self):
        if not hasattr(self, "_chat"):
            self._chat = get_chat_for_user(self.request.user, self.kwargs["chat_id"])
        return self._chat

    def get_queryset(self):
        chat = self.get_chat()
        participant = ChatService.get_active_participation(self.request.user, chat.pk)
        queryset = (
            Message.objects.filter(chat=self.get_chat())
            .select_related("sender", "reply_to")
            .prefetch_related("attachments")
            .order_by("-created_at", "-id")
        )
        if participant.history_cleared_at:
            queryset = queryset.filter(created_at__gt=participant.history_cleared_at)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MessageCreateSerializer
        return ChatMessageSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["chat"] = self.get_chat()
        return context

    def create(self, request, *args, **kwargs):
        chat = self.get_chat()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatService.create_message(
            chat,
            request.user,
            text=serializer.validated_data["text"],
            message_type=serializer.validated_data["message_type"],
            reply_to=serializer.validated_data.get("reply_to"),
        )
        events.broadcast_message_created(message)
        return Response(
            ChatMessageSerializer(message, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Chat"])
class ChatMessageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_message(self, request, message_id: int) -> Message:
        return get_object_or_404(message_queryset_for_user(request.user), pk=message_id)

    def patch(self, request, message_id: int):
        message = self.get_message(request, message_id)
        serializer = MessageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatService.update_message(message, request.user, serializer.validated_data["text"])
        events.broadcast_message_updated(message)
        return Response(ChatMessageSerializer(message, context={"request": request}).data)

    def delete(self, request, message_id: int):
        message = self.get_message(request, message_id)
        message = ChatService.delete_message(message, request.user)
        events.broadcast_message_deleted(message)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Chat"])
class MessageReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id: int):
        message = get_object_or_404(message_queryset_for_user(request.user), pk=message_id)
        if message.chat.is_read_only or message.message_type == Message.TypeChoices.SYSTEM:
            raise ValidationError("Official administration messages cannot be reported.")
        if message.sender_id == request.user.pk:
            raise ValidationError("You cannot report your own message.")
        if message.is_deleted:
            raise ValidationError("A deleted message cannot be reported.")
        serializer = MessageReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if MessageReport.objects.filter(message=message, reporter=request.user).exists():
            raise ValidationError("You have already reported this message.")
        report = MessageReport.objects.create(
            message=message,
            reporter=request.user,
            message_text=message.text,
            **serializer.validated_data,
        )
        return Response(
            MessageReportSerializer(report, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Chat"])
class ModeratorMessageReportListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageReportSerializer

    def get_queryset(self):
        if self.request.user.role != "moderator":
            raise PermissionDenied("Only moderators can view message reports.")
        return MessageReport.objects.select_related(
            "reporter", "message", "message__sender", "message__chat"
        ).prefetch_related("message__attachments")


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
        actions = ChatModerationAction.objects.filter(target_user=target).select_related(
            "moderator", "report"
        )[:100]
        warning_states = {}
        warning_actions = ChatModerationAction.objects.filter(
            target_user=target,
            report__isnull=False,
            action__in=[
                ChatModerationAction.ActionChoices.WARNING,
                ChatModerationAction.ActionChoices.RETRACT_WARNING,
            ],
        ).values_list("report_id", "action").order_by("-created_at", "-id")
        for report_id, warning_action in warning_actions:
            warning_states.setdefault(report_id, warning_action)
        return {
            "user_id": target.pk,
            "is_restricted": bool(restriction and restriction.is_active),
            "restriction_reason": restriction.reason if restriction and restriction.is_active else "",
            "restricted_at": restriction.restricted_at if restriction and restriction.is_active else None,
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
        if action in {
            ChatModerationAction.ActionChoices.WARNING,
            ChatModerationAction.ActionChoices.RETRACT_WARNING,
        } and report is None:
            raise ValidationError("A report is required for warning actions.")

        official_chat = None
        official_participant = None
        official_participant_created = False
        official_message = None
        with transaction.atomic():
            restriction = ChatUserRestriction.objects.select_for_update().filter(user=target).first()
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
                latest_warning_action = ChatModerationAction.objects.filter(
                    target_user=target,
                    report=report,
                    action__in=[
                        ChatModerationAction.ActionChoices.WARNING,
                        ChatModerationAction.ActionChoices.RETRACT_WARNING,
                    ],
                ).order_by("-created_at", "-id").first()
                if (
                    latest_warning_action
                    and latest_warning_action.action == ChatModerationAction.ActionChoices.WARNING
                ):
                    raise ValidationError("A warning is already active for this report.")
                title = "Moderator warning"
                body = note or "A moderator has issued a warning about your chat activity."
            else:
                latest_warning_action = ChatModerationAction.objects.filter(
                    target_user=target,
                    report=report,
                    action__in=[
                        ChatModerationAction.ActionChoices.WARNING,
                        ChatModerationAction.ActionChoices.RETRACT_WARNING,
                    ],
                ).order_by("-created_at", "-id").first()
                if (
                    not latest_warning_action
                    or latest_warning_action.action
                    != ChatModerationAction.ActionChoices.WARNING
                ):
                    raise ValidationError("There is no active warning for this report.")
                title = "Moderator warning retracted"
                body = note or "A moderator has retracted the warning about your chat activity."

            moderation_action = ChatModerationAction.objects.create(
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
                ) = ChatService.create_official_warning_message(target, report, note)
            NotificationService.create(
                recipient=target,
                type=Notification.TypeChoices.MODERATION_ACTION,
                title=title,
                body=body,
                link_url=f"/{target.role}-dashboard/chats",
                actor=request.user,
                payload={
                    "moderation_action_id": moderation_action.pk,
                    "action": action,
                    "report_id": report.pk if report else None,
                },
            )

        if official_participant_created and official_chat and official_participant:
            events.broadcast_participant_added(official_chat, official_participant)
        if official_message:
            events.broadcast_message_created(official_message)

        return Response(self.response_data(request, target), status=status.HTTP_201_CREATED)


@extend_schema(tags=["Chat"])
class ChatParticipantListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        participants = (
            ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
            .select_related("user")
            .order_by("joined_at", "id")
        )
        return Response(
            ChatParticipantSerializer(
                participants,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        if not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can add participants.")
        serializer = ParticipantAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participants = ChatService.add_participants(chat, serializer.validated_data["user_ids"])
        for participant in participants:
            events.broadcast_participant_added(chat, participant)
        return Response(
            ChatParticipantSerializer(
                participants,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Chat"])
class ChatParticipantDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, chat_id: int, user_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        removing_self = request.user.pk == user_id
        if not removing_self and not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can remove participants.")
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError("Participants can only be removed from group chats.")
        participant = ChatService.remove_participant(chat, user_id)
        events.broadcast_participant_removed(chat, participant)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Chat"])
class ChatParticipantRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, chat_id: int, user_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError("Participant roles only apply to group chats.")
        if not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can update roles.")
        serializer = ParticipantRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant = ChatService.update_participant_role(
            chat,
            user_id,
            serializer.validated_data["role"],
        )
        events.broadcast_chat_updated(chat.pk)
        return Response(
            ChatParticipantSerializer(participant, context={"request": request}).data
        )


@extend_schema(tags=["Chat"])
class ChatReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        serializer = ReadStatusSerializer(data=request.data, context={"chat": chat})
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data.get("message_id")
        participant = ChatService.mark_read(chat, request.user, message)
        events.broadcast_read(
            chat.pk,
            request.user.pk,
            participant.last_read_message_id,
        )
        return Response(
            ChatParticipantSerializer(participant, context={"request": request}).data
        )


@extend_schema(tags=["Chat"])
class ChatMessageAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id: int):
        ChatService.assert_can_write(request.user)
        message = get_object_or_404(message_queryset_for_user(request.user), pk=message_id)
        if message.sender_id != request.user.pk:
            raise PermissionDenied("Only the sender can attach files to this message.")
        if message.is_deleted:
            raise ValidationError("Deleted messages cannot receive attachments.")
        serializer = MessageAttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]
        attachment = MessageAttachment.objects.create(
            message=message,
            file=uploaded_file,
            file_type=getattr(uploaded_file, "content_type", "") or "application/octet-stream",
            size=uploaded_file.size,
        )
        events.broadcast_message_updated(message)
        return Response(
            ChatMessageAttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
