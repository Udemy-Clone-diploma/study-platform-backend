from django.conf import settings
from django.db import models

from apps.common.files import UUIDUploadTo


class ChatRoom(models.Model):
    class TypeChoices(models.TextChoices):
        DIRECT = "direct", "Direct"
        GROUP = "group", "Group"

    type = models.CharField(max_length=12, choices=TypeChoices.choices)
    title = models.CharField(max_length=255, blank=True, default="")
    image = models.ImageField(upload_to=UUIDUploadTo("chat/rooms"), null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_chat_rooms",
        null=True,
        blank=True,
    )
    last_message = models.ForeignKey(
        "chat.Message",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    direct_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    is_read_only = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_rooms"
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["type", "-updated_at"], name="chat_room_type_updated_idx"),
            models.Index(fields=["direct_key"], name="chat_room_direct_key_idx"),
        ]

    def __str__(self):
        return self.title or f"{self.type} chat {self.pk}"


class ChatParticipant(models.Model):
    class RoleChoices(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    chat = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_participations",
    )
    role = models.CharField(
        max_length=12,
        choices=RoleChoices.choices,
        default=RoleChoices.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    history_cleared_at = models.DateTimeField(null=True, blank=True)
    last_read_message = models.ForeignKey(
        "chat.Message",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_participants"
        ordering = ["joined_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chat", "user"],
                name="unique_chat_participant",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "left_at"], name="chat_part_user_left_idx"),
            models.Index(fields=["chat", "left_at"], name="chat_part_chat_left_idx"),
            models.Index(fields=["chat", "role"], name="chat_part_chat_role_idx"),
        ]

    @property
    def is_active(self) -> bool:
        return self.left_at is None

    def __str__(self):
        return f"{self.user_id} in chat {self.chat_id}"


class ChatUserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_blocks_created",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_user_blocks"
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_chat_user_block",
            ),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="prevent_self_chat_user_block",
            ),
        ]
        indexes = [
            models.Index(fields=["blocker", "blocked"], name="chat_block_pair_idx"),
            models.Index(fields=["blocked"], name="chat_block_blocked_idx"),
        ]

    def __str__(self):
        return f"{self.blocker_id} blocked {self.blocked_id}"


class Message(models.Model):
    class TypeChoices(models.TextChoices):
        TEXT = "text", "Text"
        FILE = "file", "File"
        IMAGE = "image", "Image"
        SYSTEM = "system", "System"

    chat = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sent_chat_messages",
        null=True,
        blank=True,
    )
    text = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=12,
        choices=TypeChoices.choices,
        default=TypeChoices.TEXT,
    )
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="replies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["chat", "created_at", "id"], name="chat_msg_chat_created_idx"),
            models.Index(fields=["chat", "id"], name="chat_msg_chat_id_idx"),
            models.Index(fields=["sender", "-created_at"], name="chat_msg_sender_created_idx"),
        ]

    def __str__(self):
        return f"message {self.pk} in chat {self.chat_id}"


class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=UUIDUploadTo("chat/attachments"))
    file_type = models.CharField(max_length=128)
    size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_message_attachments"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["message"], name="chat_attachment_message_idx"),
        ]

    def __str__(self):
        return f"attachment {self.pk} for message {self.message_id}"


class MessageReport(models.Model):
    class ReasonChoices(models.TextChoices):
        SPAM = "spam", "Spam or advertising"
        HARASSMENT = "harassment", "Harassment or bullying"
        HATE = "hate", "Hate speech"
        VIOLENCE = "violence", "Violence or threats"
        SEXUAL = "sexual", "Sexual content"
        FRAUD = "fraud", "Fraud or scam"
        OTHER = "other", "Other"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_chat_messages",
    )
    reason = models.CharField(max_length=24, choices=ReasonChoices.choices)
    details = models.CharField(max_length=500, blank=True, default="")
    message_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_message_reports"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "reporter"],
                name="unique_message_reporter",
            ),
        ]
        indexes = [
            models.Index(fields=["-created_at"], name="chat_report_created_idx"),
        ]

    def __str__(self):
        return f"report {self.pk} for message {self.message_id}"


class ChatUserRestriction(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_restriction",
    )
    restricted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="chat_restrictions_created",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    restricted_at = models.DateTimeField(auto_now_add=True)
    lifted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_user_restrictions"
        indexes = [
            models.Index(fields=["is_active"], name="chat_restrict_active_idx"),
        ]

    def __str__(self):
        return f"chat restriction for user {self.user_id}"


class ChatModerationAction(models.Model):
    class ActionChoices(models.TextChoices):
        WARNING = "warning", "Warning"
        RETRACT_WARNING = "retract_warning", "Warning retracted"
        RESTRICT = "restrict", "Chat access restricted"
        RESTORE = "restore", "Chat access restored"

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_moderation_actions_received",
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="chat_moderation_actions_created",
        null=True,
        blank=True,
    )
    report = models.ForeignKey(
        MessageReport,
        on_delete=models.SET_NULL,
        related_name="moderation_actions",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=16, choices=ActionChoices.choices)
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_moderation_actions"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["target_user", "-created_at"],
                name="chat_mod_user_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action} for user {self.target_user_id}"
