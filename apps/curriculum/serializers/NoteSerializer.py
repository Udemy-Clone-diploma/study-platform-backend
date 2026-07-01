from rest_framework import serializers


class NoteSerializer(serializers.Serializer):
    content = serializers.CharField(allow_blank=True, trim_whitespace=False)
