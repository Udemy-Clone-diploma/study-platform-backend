from rest_framework import serializers


class AdminNoteSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=2000)
    updated_at = serializers.DateTimeField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)
