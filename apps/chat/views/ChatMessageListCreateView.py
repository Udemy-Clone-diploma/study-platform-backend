from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat import events
from apps.chat.models import Message
from apps.chat.serializers import ChatMessageSerializer, MessageCreateSerializer
from apps.chat.services import ChatService

from .utils import get_chat_for_user


@extend_schema(tags=["Chat"])
class ChatMessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_chat(self):
        if not hasattr(self, "_chat"):
            self._chat = get_chat_for_user(
                self.request.user,
                self.kwargs["chat_id"],
            )
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
            ChatMessageSerializer(
                message,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
