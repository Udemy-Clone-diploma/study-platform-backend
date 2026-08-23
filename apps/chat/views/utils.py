import re

from django.shortcuts import get_object_or_404

from apps.chat.models import ChatRoom, Message


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


CHAT_LINK_PATTERN = re.compile(r"https?://[^\s<>()]+")


def chat_message_links(text: str) -> list[str]:
    links = []
    for match in CHAT_LINK_PATTERN.findall(text or ""):
        link = match.rstrip(".,!?;:)]}")
        if link and link not in links:
            links.append(link)
    return links


def chat_attachment_kind(file_type: str) -> str:
    if file_type.startswith("image/"):
        return "image"
    if file_type.startswith("video/"):
        return "video"
    if file_type == "text/uri-list":
        return "link"
    return "file"
