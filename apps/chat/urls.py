from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.chat.views import (
    ChatAttachmentListView,
    ChatMessageAttachmentView,
    ChatMessageDetailView,
    ChatMessageListCreateView,
    ChatParticipantDetailView,
    ChatParticipantListCreateView,
    ChatParticipantRoleView,
    ChatReadView,
    ChatRoomViewSet,
    MessageReportCreateView,
    ModeratorChatUserActionView,
    ModeratorMessageReportListView,
)

router = DefaultRouter()
router.register(r"chats", ChatRoomViewSet, basename="chats")

urlpatterns = [
    path(
        "chats/<int:chat_id>/messages/", ChatMessageListCreateView.as_view(), name="chat-messages"
    ),
    path(
        "chats/<int:chat_id>/attachments/",
        ChatAttachmentListView.as_view(),
        name="chat-attachments",
    ),
    path("messages/<int:message_id>/", ChatMessageDetailView.as_view(), name="chat-message-detail"),
    path(
        "messages/<int:message_id>/report/",
        MessageReportCreateView.as_view(),
        name="chat-message-report",
    ),
    path(
        "moderation/message-reports/",
        ModeratorMessageReportListView.as_view(),
        name="moderator-message-reports",
    ),
    path(
        "moderation/users/<int:user_id>/",
        ModeratorChatUserActionView.as_view(),
        name="moderator-chat-user-action",
    ),
    path(
        "messages/<int:message_id>/attachments/",
        ChatMessageAttachmentView.as_view(),
        name="chat-message-attachments",
    ),
    path(
        "chats/<int:chat_id>/participants/",
        ChatParticipantListCreateView.as_view(),
        name="chat-participants",
    ),
    path(
        "chats/<int:chat_id>/participants/<int:user_id>/",
        ChatParticipantDetailView.as_view(),
        name="chat-participant-detail",
    ),
    path(
        "chats/<int:chat_id>/participants/<int:user_id>/role/",
        ChatParticipantRoleView.as_view(),
        name="chat-participant-role",
    ),
    path("chats/<int:chat_id>/read/", ChatReadView.as_view(), name="chat-read"),
    path("", include(router.urls)),
]
