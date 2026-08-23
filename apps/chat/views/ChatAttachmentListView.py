from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message
from apps.chat.serializers import (
    ChatMessageAttachmentSerializer,
    ChatMessageSerializer,
)
from apps.chat.services import ChatService

from .utils import (
    chat_attachment_kind,
    chat_message_links,
    get_chat_for_user,
)


@extend_schema(tags=["Chat"])
class ChatAttachmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id: int):
        chat = get_chat_for_user(request.user, chat_id)
        participant = ChatService.get_active_participation(request.user, chat.pk)
        messages = (
            Message.objects.filter(chat=chat, is_deleted=False)
            .select_related("sender", "reply_to")
            .prefetch_related("attachments")
            .order_by("-created_at", "-id")
        )
        if participant.history_cleared_at:
            messages = messages.filter(
                created_at__gt=participant.history_cleared_at
            )

        results = []
        for message in messages:
            message_data = ChatMessageSerializer(
                message,
                context={"request": request},
            ).data
            for attachment in message.attachments.all():
                attachment_data = ChatMessageAttachmentSerializer(
                    attachment,
                    context={"request": request},
                ).data
                attachment_data.update(
                    {
                        "kind": chat_attachment_kind(attachment.file_type),
                        "message": message_data,
                    }
                )
                results.append(attachment_data)

            for link_index, link in enumerate(chat_message_links(message.text)):
                results.append(
                    {
                        "id": f"link-{message.pk}-{link_index}",
                        "url": link,
                        "file_type": "text/uri-list",
                        "size": 0,
                        "created_at": message.created_at,
                        "kind": "link",
                        "message": message_data,
                    }
                )

        return Response(results)
