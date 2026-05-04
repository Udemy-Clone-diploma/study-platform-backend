from rest_framework import serializers


class EmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
