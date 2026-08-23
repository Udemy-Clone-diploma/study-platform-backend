from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.serializers import ChatParticipantSerializer, ReadStatusSerializer
from apps.chat.services import ChatService

from .utils import get_chat_for_user


@extend_schema(tags=["Chat"])
class ChatReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        serializer = ReadStatusSerializer(data=request.data, context={"chat": chat})
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data.get("message_id")
        participant = ChatService.mark_read(chat, request.user, message)
        events.broadcast_read(
            chat.pk,
            request.user.pk,
            participant.last_read_message_id,
        )
        return Response(
            ChatParticipantSerializer(participant, context={"request": request}).data
        )
