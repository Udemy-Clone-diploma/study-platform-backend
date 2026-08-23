from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import ChatParticipant
from apps.chat.serializers import ChatParticipantSerializer, ParticipantAddSerializer
from apps.chat.services import ChatService

from .utils import get_chat_for_user


@extend_schema(tags=["Chat"])
class ChatParticipantListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        participants = (
            ChatParticipant.objects.filter(chat=chat, left_at__isnull=True)
            .select_related("user")
            .order_by("joined_at", "id")
        )
        return Response(
            ChatParticipantSerializer(
                participants,
                many=True,
                context={"request": request},
            ).data
        )

    def post(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        if not ChatService.can_manage_participants(request.user, chat):
            raise PermissionDenied("Only group owners and admins can add participants.")
        serializer = ParticipantAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participants = ChatService.add_participants(
            chat,
            serializer.validated_data["user_ids"],
        )
        for participant in participants:
            events.broadcast_participant_added(chat, participant)
        return Response(
            ChatParticipantSerializer(
                participants,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
