import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from apps.chat.models import ChatParticipant, ChatRoom, Message
from apps.chat.serializers import ChatMessageSerializer, ChatRoomSerializer

logger = logging.getLogger(__name__)


def chat_group_name(chat_id: int) -> str:
    return f"chat_{chat_id}"


def user_group_name(user_id: int) -> str:
    return f"user_{user_id}"


@shared_task
def _send(group: str, payload: dict):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "chat.event",
                "payload": payload,
            },
        )
    except Exception:
        # A broker outage must not turn an otherwise successful HTTP action
        # (such as uploading an attachment) into a 500 response.
        logger.warning("Could not publish chat event to %s", group, exc_info=True)


def _message_payload(message: Message) -> dict:
    message = (
        Message.objects.select_related("chat", "sender", "reply_to")
        .prefetch_related("attachments")
        .get(pk=message.pk)
    )
    return ChatMessageSerializer(message).data


def broadcast_chat_updated(chat_id: int):
    try:
        chat = (
            ChatRoom.objects.select_related("created_by", "last_message", "last_message__sender")
            .prefetch_related("participants__user")
            .get(pk=chat_id, is_deleted=False)
        )
    except ChatRoom.DoesNotExist:
        return

    participants = (
        ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
        .select_related("user")
        .order_by("id")
    )
    for participant in participants:
        _send.delay(
            user_group_name(participant.user_id),
            {
                "type": "chat.updated",
                "chat": ChatRoomSerializer(chat, context={"user": participant.user}).data,
            },
        )


def broadcast_chat_deleted(chat_id: int, user_ids: list[int]):
    payload = {
        "type": "chat.deleted",
        "chat_id": chat_id,
    }
    _send.delay(chat_group_name(chat_id), payload)
    for user_id in user_ids:
        _send.delay(user_group_name(user_id), payload)


def broadcast_message_created(message: Message):
    _send.delay(
        chat_group_name(message.chat_id),
        {
            "type": "message.created",
            "message": _message_payload(message),
        },
    )
    broadcast_chat_updated(message.chat_id)


def broadcast_message_updated(message: Message):
    _send.delay(
        chat_group_name(message.chat_id),
        {
            "type": "message.updated",
            "message": _message_payload(message),
        },
    )
    broadcast_chat_updated(message.chat_id)


def broadcast_message_deleted(message: Message):
    _send.delay(
        chat_group_name(message.chat_id),
        {
            "type": "message.deleted",
            "message": _message_payload(message),
        },
    )
    broadcast_chat_updated(message.chat_id)


def broadcast_read(chat_id: int, user_id: int, message_id: int | None):
    _send.delay(
        chat_group_name(chat_id),
        {
            "type": "message.read",
            "chat_id": chat_id,
            "user_id": user_id,
            "message_id": message_id,
        },
    )
    broadcast_chat_updated(chat_id)


def broadcast_participant_added(chat: ChatRoom, participant: ChatParticipant):
    payload = {
        "type": "participant.added",
        "chat_id": chat.pk,
        "participant": {
            "user_id": participant.user_id,
            "role": participant.role,
        },
    }
    _send.delay(chat_group_name(chat.pk), payload)
    _send.delay(user_group_name(participant.user_id), payload)
    broadcast_chat_updated(chat.pk)


def broadcast_participant_removed(chat: ChatRoom, participant: ChatParticipant):
    payload = {
        "type": "participant.removed",
        "chat_id": chat.pk,
        "user_id": participant.user_id,
    }
    _send.delay(chat_group_name(chat.pk), payload)
    _send.delay(user_group_name(participant.user_id), payload)
    broadcast_chat_updated(chat.pk)
