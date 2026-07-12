from django.contrib import admin

from apps.chat.models import (
    ChatModerationAction,
    ChatParticipant,
    ChatRoom,
    ChatUserBlock,
    ChatUserRestriction,
    Message,
    MessageAttachment,
    MessageReport,
)


class ChatParticipantInline(admin.TabularInline):
    model = ChatParticipant
    extra = 0
    autocomplete_fields = ["user", "last_read_message"]


class MessageAttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "title", "created_by", "last_message", "is_read_only", "is_deleted", "updated_at"]
    list_filter = ["type", "is_read_only", "is_deleted"]
    search_fields = ["title", "direct_key", "participants__user__email"]
    autocomplete_fields = ["created_by", "last_message"]
    inlines = [ChatParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "chat", "sender", "message_type", "is_deleted", "created_at"]
    list_filter = ["message_type", "is_deleted"]
    search_fields = ["text", "sender__email", "chat__title"]
    autocomplete_fields = ["chat", "sender", "reply_to"]
    inlines = [MessageAttachmentInline]


@admin.register(ChatParticipant)
class ChatParticipantAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "chat",
        "user",
        "role",
        "left_at",
        "is_muted",
        "history_cleared_at",
        "updated_at",
    ]
    list_filter = ["role", "is_muted", "left_at"]
    search_fields = ["chat__title", "user__email"]
    autocomplete_fields = ["chat", "user", "last_read_message"]


@admin.register(ChatUserBlock)
class ChatUserBlockAdmin(admin.ModelAdmin):
    list_display = ["id", "blocker", "blocked", "created_at"]
    search_fields = ["blocker__email", "blocked__email"]
    autocomplete_fields = ["blocker", "blocked"]


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ["id", "message", "file_type", "size", "created_at"]
    search_fields = ["message__text", "file_type"]
    autocomplete_fields = ["message"]


@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ["id", "message", "reporter", "reason", "created_at"]
    list_filter = ["reason"]
    search_fields = ["message_text", "reporter__email", "message__sender__email"]
    autocomplete_fields = ["message", "reporter"]


@admin.register(ChatUserRestriction)
class ChatUserRestrictionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "is_active", "restricted_by", "restricted_at", "lifted_at"]
    list_filter = ["is_active"]
    search_fields = ["user__email", "restricted_by__email", "reason"]
    autocomplete_fields = ["user", "restricted_by"]


@admin.register(ChatModerationAction)
class ChatModerationActionAdmin(admin.ModelAdmin):
    list_display = ["id", "target_user", "action", "moderator", "report", "created_at"]
    list_filter = ["action"]
    search_fields = ["target_user__email", "moderator__email", "note"]
    autocomplete_fields = ["target_user", "moderator", "report"]
