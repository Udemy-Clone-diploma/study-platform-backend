from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import ChatRoom
from apps.chat.serializers import (
    ChatParticipantSerializer,
    ParticipantRoleUpdateSerializer,
)
from apps.chat.services import ChatService

from .utils import get_chat_for_user


@extend_schema(tags=["Chat"])
class ChatParticipantRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, chat_id: int, user_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError("Participant roles only apply to group chats.")
        if not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can update roles.")
        serializer = ParticipantRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant = ChatService.update_participant_role(
            chat,
            user_id,
            serializer.validated_data["role"],
        )
        events.broadcast_chat_updated(chat.pk)
        return Response(ChatParticipantSerializer(participant, context={"request": request}).data)
