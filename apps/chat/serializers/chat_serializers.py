from django.conf import settings
from rest_framework import serializers

from apps.chat.models import (
    ChatModerationAction,
    ChatParticipant,
    ChatRoom,
    ChatUserBlock,
    Message,
    MessageAttachment,
    MessageReport,
)
from apps.chat.services import ChatService
from apps.common.files import absolute_media_url
from apps.users.models import User

from .chat_user_serializers import (
    ModerationChatUserSerializer,
    PublicChatUserSerializer,
)


class ChatMessageAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = ["id", "url", "file_type", "size", "created_at"]

    def get_url(self, obj) -> str | None:
        return absolute_media_url(obj.file, self.context.get("request"))


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = PublicChatUserSerializer(read_only=True)
    attachments = ChatMessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "chat",
            "sender",
            "text",
            "message_type",
            "reply_to",
            "created_at",
            "edited_at",
            "deleted_at",
            "is_deleted",
            "attachments",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_deleted:
            data["text"] = ""
            data["attachments"] = []
        return data


class MessageReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageReport
        fields = ["reason", "details"]


class MessageReportSerializer(serializers.ModelSerializer):
    reporter = ModerationChatUserSerializer(read_only=True)
    sender = serializers.SerializerMethodField()
    chat = serializers.SerializerMethodField()
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    message_created_at = serializers.DateTimeField(source="message.created_at", read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = MessageReport
        fields = [
            "id", "reason", "reason_label", "details", "message_text", "created_at",
            "message", "message_created_at", "sender", "reporter", "chat", "attachments",
        ]
        read_only_fields = fields

    def get_sender(self, obj):
        if obj.message.sender is None:
            return None
        return ModerationChatUserSerializer(
            obj.message.sender,
            context=self.context,
        ).data

    def get_chat(self, obj):
        chat = obj.message.chat
        return {"id": chat.pk, "type": chat.type, "title": chat.title}

    def get_attachments(self, obj):
        return ChatMessageAttachmentSerializer(
            obj.message.attachments.all(), many=True, context=self.context
        ).data


class ChatModerationActionSerializer(serializers.ModelSerializer):
    moderator = ModerationChatUserSerializer(read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ChatModerationAction
        fields = [
            "id",
            "action",
            "action_label",
            "note",
            "report",
            "moderator",
            "created_at",
        ]
        read_only_fields = fields


class ChatModerationRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ChatModerationAction.ActionChoices.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    report_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class ChatParticipantSerializer(serializers.ModelSerializer):
    user = PublicChatUserSerializer(read_only=True)
    last_read_message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ChatParticipant
        fields = [
            "id",
            "chat",
            "user",
            "role",
            "joined_at",
            "left_at",
            "is_muted",
            "history_cleared_at",
            "last_read_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "chat",
            "user",
            "joined_at",
            "left_at",
            "history_cleared_at",
            "last_read_message",
            "created_at",
            "updated_at",
        ]


class ChatRoomSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    created_by = PublicChatUserSerializer(read_only=True)
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    blocked_user_ids = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "type",
            "title",
            "image",
            "image_url",
            "created_by",
            "participants",
            "last_message",
            "unread_count",
            "blocked_user_ids",
            "is_read_only",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "type",
            "image_url",
            "created_by",
            "participants",
            "last_message",
            "unread_count",
            "blocked_user_ids",
            "is_read_only",
            "created_at",
            "updated_at",
        ]

    def _current_participation(self, obj) -> ChatParticipant | None:
        request = self.context.get("request")
        user = self.context.get("user") or getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        return (
            ChatParticipant.objects.filter(chat=obj, user=user, left_at__isnull=True)
            .select_related("last_read_message")
            .first()
        )

    def get_image_url(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_participants(self, obj):
        participants = (
            obj.participants.filter(left_at__isnull=True)
            .select_related("user")
            .order_by("joined_at", "id")
        )
        return ChatParticipantSerializer(participants, many=True, context=self.context).data

    def get_last_message(self, obj):
        participation = self._current_participation(obj)
        if participation and participation.history_cleared_at:
            message = (
                Message.objects.filter(chat=obj, created_at__gt=participation.history_cleared_at)
                .select_related("sender", "reply_to")
                .prefetch_related("attachments")
                .order_by("-created_at", "-id")
                .first()
            )
        else:
            message = obj.last_message

        if message is None:
            return None
        return ChatMessageSerializer(message, context=self.context).data

    def get_unread_count(self, obj) -> int:
        request = self.context.get("request")
        user = self.context.get("user") or getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return 0

        participation = self._current_participation(obj)
        if participation is None:
            return 0

        messages = Message.objects.filter(chat=obj, is_deleted=False).exclude(sender=user)
        if participation.history_cleared_at:
            messages = messages.filter(created_at__gt=participation.history_cleared_at)
        if participation.last_read_message_id:
            messages = messages.filter(id__gt=participation.last_read_message_id)
        return messages.count()

    def get_blocked_user_ids(self, obj) -> list[int]:
        request = self.context.get("request")
        user = self.context.get("user") or getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        participant_user_ids = obj.participants.filter(left_at__isnull=True).values_list(
            "user_id",
            flat=True,
        )
        return list(
            ChatUserBlock.objects.filter(
                blocker=user,
                blocked_id__in=participant_user_ids,
            ).values_list("blocked_id", flat=True)
        )


class DirectChatCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)

    def validate_user_id(self, value):
        request = self.context["request"]
        if value == request.user.pk:
            raise serializers.ValidationError("You cannot start a direct chat with yourself.")
        try:
            return User.objects.get(pk=value, is_deleted=False)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("User does not exist.") from exc

    def save(self, **kwargs):
        request = self.context["request"]
        other_user = self.validated_data["user_id"]
        chat, created = ChatService.create_direct_chat(request.user, other_user)
        self.created = created
        return chat


class GroupChatCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, trim_whitespace=True)
    image = serializers.ImageField(required=False, allow_null=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_participant_ids(self, value):
        request = self.context["request"]
        participant_ids = list(dict.fromkeys(value))
        if request.user.pk in participant_ids:
            participant_ids.remove(request.user.pk)
        existing_count = User.objects.filter(pk__in=participant_ids, is_deleted=False).count()
        if existing_count != len(participant_ids):
            raise serializers.ValidationError("One or more users do not exist.")
        return participant_ids

    def save(self, **kwargs):
        request = self.context["request"]
        return ChatService.create_group_chat(
            request.user,
            self.validated_data["title"],
            self.validated_data["participant_ids"],
            image=self.validated_data.get("image"),
        )


class MessageCreateSerializer(serializers.Serializer):
    text = serializers.CharField(
        max_length=getattr(settings, "CHAT_MESSAGE_MAX_LENGTH", 4000),
        trim_whitespace=True,
        allow_blank=False,
    )
    message_type = serializers.ChoiceField(
        choices=Message.TypeChoices.choices,
        default=Message.TypeChoices.TEXT,
    )
    reply_to = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_reply_to(self, value):
        if value is None:
            return None
        chat = self.context["chat"]
        try:
            return Message.objects.get(pk=value, chat=chat)
        except Message.DoesNotExist as exc:
            raise serializers.ValidationError("Reply target does not exist in this chat.") from exc


class MessageUpdateSerializer(serializers.Serializer):
    text = serializers.CharField(
        max_length=getattr(settings, "CHAT_MESSAGE_MAX_LENGTH", 4000),
        trim_whitespace=True,
        allow_blank=False,
    )


class ParticipantAddSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_user_ids(self, value):
        return list(dict.fromkeys(value))


class ParticipantRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            ChatParticipant.RoleChoices.ADMIN,
            ChatParticipant.RoleChoices.MEMBER,
        ]
    )


class ReadStatusSerializer(serializers.Serializer):
    message_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate_message_id(self, value):
        if value is None:
            return None
        chat = self.context["chat"]
        try:
            return Message.objects.get(pk=value, chat=chat)
        except Message.DoesNotExist as exc:
            raise serializers.ValidationError("Message does not exist in this chat.") from exc


class ChatMuteSerializer(serializers.Serializer):
    is_muted = serializers.BooleanField()


class ChatBlockSerializer(serializers.Serializer):
    is_blocked = serializers.BooleanField()


class MessageAttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)

    def validate_file(self, uploaded_file):
        max_bytes = getattr(settings, "CHAT_ATTACHMENT_MAX_BYTES", 25 * 1024 * 1024)
        allowed_types = getattr(settings, "CHAT_ATTACHMENT_ALLOWED_TYPES", [])

        if uploaded_file.size > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise serializers.ValidationError(
                f"A chat attachment cannot exceed {max_mb} MB."
            )

        content_type = getattr(uploaded_file, "content_type", "") or ""
        if allowed_types and content_type not in allowed_types:
            raise serializers.ValidationError("This attachment type is not allowed.")

        return uploaded_file
