from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import StudentProfile, User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, validators=[validate_password]
    )
    date_of_birth = serializers.DateField(write_only=True, required=False)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "date_of_birth",
            "first_name",
            "last_name",
            "role",
            "language",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        date_of_birth = validated_data.pop("date_of_birth", None)
        validated_data["role"] = "student"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        StudentProfile.objects.create(user=user, date_of_birth=date_of_birth)
        return user
