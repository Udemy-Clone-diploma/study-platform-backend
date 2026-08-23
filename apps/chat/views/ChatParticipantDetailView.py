from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import ChatRoom
from apps.chat.services import ChatService

from .utils import get_chat_for_user


@extend_schema(tags=["Chat"])
class ChatParticipantDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, chat_id: int, user_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        removing_self = request.user.pk == user_id
        if not removing_self and not ChatService.can_manage_participants(
            request.user,
            chat,
        ):
            raise PermissionDenied(
                "Only group owners and admins can remove participants."
            )
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError(
                "Participants can only be removed from group chats."
            )
        participant = ChatService.remove_participant(chat, user_id)
        events.broadcast_participant_removed(chat, participant)
        return Response(status=status.HTTP_204_NO_CONTENT)
