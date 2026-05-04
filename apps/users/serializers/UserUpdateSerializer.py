from rest_framework import serializers

from apps.users.models import User


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "avatar", "language"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():  # type: ignore
            raise serializers.ValidationError("A user with this email already exists.")
        return value
