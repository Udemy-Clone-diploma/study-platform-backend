from rest_framework import serializers

from apps.payments.models import WebhookEvent


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "provider",
            "event_id",
            "event_type",
            "status",
            "processed_at",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
