import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import APIException

from apps.chat import events
from apps.chat.models import ChatParticipant, ChatRoom, Message
from apps.chat.serializers import MessageCreateSerializer, MessageUpdateSerializer
from apps.chat.services import ChatService
from apps.chat.views.chat_views import get_chat_for_user, message_queryset_for_user


ONLINE_USER_CONNECTIONS: dict[int, int] = {}


def _mark_user_connected(user_id: int) -> bool:
    ONLINE_USER_CONNECTIONS[user_id] = ONLINE_USER_CONNECTIONS.get(user_id, 0) + 1
    return ONLINE_USER_CONNECTIONS[user_id] == 1


def _mark_user_disconnected(user_id: int) -> bool:
    connection_count = ONLINE_USER_CONNECTIONS.get(user_id, 0)
    if connection_count <= 1:
        ONLINE_USER_CONNECTIONS.pop(user_id, None)
        return True
    ONLINE_USER_CONNECTIONS[user_id] = connection_count - 1
    return False


def _online_user_ids(user_ids: list[int]) -> list[int]:
    return [user_id for user_id in user_ids if ONLINE_USER_CONNECTIONS.get(user_id, 0) > 0]


@database_sync_to_async
def _active_chat_ids(user) -> list[int]:
    return list(
        ChatRoom.objects.filter(
            is_deleted=False,
            participants__user=user,
            participants__left_at__isnull=True,
        )
        .distinct()
        .values_list("id", flat=True)
    )


@database_sync_to_async
def _active_chat_peer_ids(user) -> list[int]:
    return list(
        ChatParticipant.objects.filter(
            chat__is_deleted=False,
            chat__participants__user=user,
            chat__participants__left_at__isnull=True,
            left_at__isnull=True,
        )
        .exclude(user=user)
        .distinct()
        .values_list("user_id", flat=True)
    )


@database_sync_to_async
def _user_name(user) -> str:
    return user.get_full_name() or user.email


@database_sync_to_async
def _assert_active_participant(user, chat_id: int) -> bool:
    return ChatService.is_active_participant(user, chat_id)


@database_sync_to_async
def _create_message(user, payload: dict) -> int:
    chat = get_chat_for_user(user, payload.get("chat_id"))
    serializer = MessageCreateSerializer(data=payload, context={"chat": chat})
    serializer.is_valid(raise_exception=True)
    message = ChatService.create_message(
        chat,
        user,
        text=serializer.validated_data["text"],
        message_type=serializer.validated_data["message_type"],
        reply_to=serializer.validated_data.get("reply_to"),
    )
    events.broadcast_message_created(message)
    return message.pk


@database_sync_to_async
def _edit_message(user, payload: dict) -> int:
    message = message_queryset_for_user(user).get(pk=payload.get("message_id"))
    serializer = MessageUpdateSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    message = ChatService.update_message(message, user, serializer.validated_data["text"])
    events.broadcast_message_updated(message)
    return message.pk


@database_sync_to_async
def _delete_message(user, payload: dict) -> int:
    message = message_queryset_for_user(user).get(pk=payload.get("message_id"))
    message = ChatService.delete_message(message, user)
    events.broadcast_message_deleted(message)
    return message.pk


@database_sync_to_async
def _mark_read(user, payload: dict) -> int | None:
    chat = get_chat_for_user(user, payload.get("chat_id"))
    message = None
    message_id = payload.get("message_id")
    if message_id:
        message = Message.objects.get(pk=message_id, chat=chat)
    participant = ChatService.mark_read(chat, user, message)
    events.broadcast_read(chat.pk, user.pk, participant.last_read_message_id)
    return participant.last_read_message_id


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.joined_chat_ids: set[int] = set()
        self.typing_sent_at: dict[tuple[int, str], float] = {}

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_id = self.user.pk
        became_online = _mark_user_connected(self.user_id)

        await self.channel_layer.group_add(events.user_group_name(self.user.pk), self.channel_name)

        for chat_id in await _active_chat_ids(self.user):
            await self.channel_layer.group_add(events.chat_group_name(chat_id), self.channel_name)
            self.joined_chat_ids.add(chat_id)

        await self.accept()
        await self.send_json(
            {
                "type": "presence.snapshot",
                "online_user_ids": _online_user_ids(await _active_chat_peer_ids(self.user)),
            }
        )
        if became_online:
            await self._broadcast_presence(is_online=True)

    async def disconnect(self, close_code):
        if not getattr(self, "user", None) or not self.user.is_authenticated:
            return
        became_offline = _mark_user_disconnected(self.user_id)
        if became_offline:
            await self._broadcast_presence(is_online=False)
        await self.channel_layer.group_discard(events.user_group_name(self.user.pk), self.channel_name)
        for chat_id in self.joined_chat_ids:
            await self.channel_layer.group_discard(events.chat_group_name(chat_id), self.channel_name)

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        payload = content.get("payload") or content

        try:
            if event_type == "message.send":
                await self._handle_message_send(payload)
            elif event_type == "typing.start":
                await self._handle_typing(payload, is_typing=True)
            elif event_type == "typing.stop":
                await self._handle_typing(payload, is_typing=False)
            elif event_type == "message.read":
                await _mark_read(self.user, payload)
            elif event_type == "message.edit":
                await _edit_message(self.user, payload)
            elif event_type == "message.delete":
                await _delete_message(self.user, payload)
            elif event_type == "ping":
                await self.send_json({"type": "pong"})
            else:
                await self._send_error("unknown_event", "Unsupported chat event.")
        except Message.DoesNotExist:
            await self._send_error("not_found", "Message was not found.")
        except ChatRoom.DoesNotExist:
            await self._send_error("not_found", "Chat was not found.")
        except APIException as exc:
            await self._send_error("invalid_request", exc.detail)
        except Exception:
            await self._send_error("server_error", "Unable to process chat event.")

    async def _handle_message_send(self, payload: dict):
        chat_id = payload.get("chat_id")
        if not chat_id:
            await self._send_error("missing_chat_id", "chat_id is required.")
            return
        if chat_id not in self.joined_chat_ids:
            if not await _assert_active_participant(self.user, chat_id):
                await self._send_error("forbidden", "You are not a participant of this chat.")
                return
            await self.channel_layer.group_add(events.chat_group_name(chat_id), self.channel_name)
            self.joined_chat_ids.add(chat_id)
        await _create_message(self.user, payload)

    async def _handle_typing(self, payload: dict, *, is_typing: bool):
        chat_id = payload.get("chat_id")
        if not chat_id:
            await self._send_error("missing_chat_id", "chat_id is required.")
            return

        now = time.monotonic()
        key = (int(chat_id), "start" if is_typing else "stop")
        if now - self.typing_sent_at.get(key, 0) < 0.8:
            return
        self.typing_sent_at[key] = now

        if not await _assert_active_participant(self.user, chat_id):
            await self._send_error("forbidden", "You are not a participant of this chat.")
            return

        await self.channel_layer.group_send(
            events.chat_group_name(chat_id),
            {
                "type": "chat.event",
                "payload": {
                    "type": "typing",
                    "chat_id": chat_id,
                    "user": {
                        "id": self.user.pk,
                        "name": await _user_name(self.user),
                    },
                    "is_typing": is_typing,
                    "sender_channel_name": self.channel_name,
                },
            },
        )

    async def chat_event(self, event):
        payload = dict(event["payload"])
        if payload.pop("sender_channel_name", None) == self.channel_name:
            return

        if payload.get("type") == "participant.added":
            participant = payload.get("participant") or {}
            if participant.get("user_id") == self.user.pk:
                chat_id = payload.get("chat_id")
                await self.channel_layer.group_add(events.chat_group_name(chat_id), self.channel_name)
                self.joined_chat_ids.add(chat_id)

        if payload.get("type") == "participant.removed" and payload.get("user_id") == self.user.pk:
            chat_id = payload.get("chat_id")
            await self.channel_layer.group_discard(events.chat_group_name(chat_id), self.channel_name)
            self.joined_chat_ids.discard(chat_id)

        if payload.get("type") == "chat.deleted":
            chat_id = payload.get("chat_id")
            await self.channel_layer.group_discard(events.chat_group_name(chat_id), self.channel_name)
            self.joined_chat_ids.discard(chat_id)

        await self.send_json(payload)

    async def _broadcast_presence(self, *, is_online: bool):
        for chat_id in self.joined_chat_ids:
            await self.channel_layer.group_send(
                events.chat_group_name(chat_id),
                {
                    "type": "chat.event",
                    "payload": {
                        "type": "presence",
                        "user_id": self.user_id,
                        "is_online": is_online,
                        "sender_channel_name": self.channel_name,
                    },
                },
            )

    async def _send_error(self, code: str, detail):
        await self.send_json(
            {
                "type": "error",
                "code": code,
                "detail": detail,
            }
        )
