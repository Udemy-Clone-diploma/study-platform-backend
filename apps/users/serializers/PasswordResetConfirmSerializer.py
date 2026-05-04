from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )
