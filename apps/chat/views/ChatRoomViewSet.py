from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat import events
from apps.chat.models import ChatRoom
from apps.chat.serializers import (
    ChatBlockSerializer,
    ChatMuteSerializer,
    ChatParticipantSerializer,
    ChatRoomSerializer,
    DirectChatCreateSerializer,
    GroupChatCreateSerializer,
)
from apps.chat.services import ChatService

from .utils import chat_queryset_for_user


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
            ChatParticipantSerializer(
                participant,
                context=self.get_serializer_context(),
            ).data
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
