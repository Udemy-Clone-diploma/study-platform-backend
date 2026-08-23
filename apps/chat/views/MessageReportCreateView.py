from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message, MessageReport
from apps.chat.serializers import (
    MessageReportCreateSerializer,
    MessageReportSerializer,
)

from .utils import message_queryset_for_user


@extend_schema(tags=["Chat"])
class MessageReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id: int):
        message = get_object_or_404(
            message_queryset_for_user(request.user),
            pk=message_id,
        )
        if message.chat.is_read_only or message.message_type == Message.TypeChoices.SYSTEM:
            raise ValidationError("Official administration messages cannot be reported.")
        if message.sender_id == request.user.pk:
            raise ValidationError("You cannot report your own message.")
        if message.is_deleted:
            raise ValidationError("A deleted message cannot be reported.")
        serializer = MessageReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if MessageReport.objects.filter(
            message=message,
            reporter=request.user,
        ).exists():
            raise ValidationError("You have already reported this message.")
        report = MessageReport.objects.create(
            message=message,
            reporter=request.user,
            message_text=message.text,
            **serializer.validated_data,
        )
        return Response(
            MessageReportSerializer(
                report,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
