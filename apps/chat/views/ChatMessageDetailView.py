from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import Message
from apps.chat.serializers import ChatMessageSerializer, MessageUpdateSerializer
from apps.chat.services import ChatService

from .utils import message_queryset_for_user


@extend_schema(tags=["Chat"])
class ChatMessageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_message(self, request, message_id: int) -> Message:
        return get_object_or_404(
            message_queryset_for_user(request.user),
            pk=message_id,
        )

    def patch(self, request, message_id: int):
        message = self.get_message(request, message_id)
        serializer = MessageUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatService.update_message(
            message,
            request.user,
            serializer.validated_data["text"],
        )
        events.broadcast_message_updated(message)
        return Response(
            ChatMessageSerializer(message, context={"request": request}).data
        )

    def delete(self, request, message_id: int):
        message = self.get_message(request, message_id)
        message = ChatService.delete_message(message, request.user)
        events.broadcast_message_deleted(message)
        return Response(status=status.HTTP_204_NO_CONTENT)
