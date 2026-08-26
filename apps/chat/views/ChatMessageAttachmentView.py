from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import events
from apps.chat.models import MessageAttachment
from apps.chat.serializers import (
    ChatMessageAttachmentSerializer,
    MessageAttachmentUploadSerializer,
)
from apps.chat.services import ChatService

from .utils import message_queryset_for_user


@extend_schema(tags=["Chat"])
class ChatMessageAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id: int):
        ChatService.assert_can_write(request.user)
        message = get_object_or_404(
            message_queryset_for_user(request.user),
            pk=message_id,
        )
        if message.sender_id != request.user.pk:
            raise PermissionDenied("Only the sender can attach files to this message.")
        if message.is_deleted:
            raise ValidationError("Deleted messages cannot receive attachments.")
        serializer = MessageAttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]
        attachment = MessageAttachment.objects.create(
            message=message,
            file=uploaded_file,
            file_type=(getattr(uploaded_file, "content_type", "") or "application/octet-stream"),
            size=uploaded_file.size,
        )
        events.broadcast_message_updated(message)
        return Response(
            ChatMessageAttachmentSerializer(
                attachment,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
