from rest_framework import serializers

from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile, User
from django.contrib.auth.password_validation import validate_password

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ["date_of_birth", "learning_goals", "education_level"]


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = ["bio", "experience", "specialization"]


class ModeratorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratorProfile
        fields = ["level"]


PROFILE_SERIALIZERS = {
    "student": StudentProfileSerializer,
    "teacher": TeacherProfileSerializer,
    "moderator": ModeratorProfileSerializer,
}

PROFILE_MODELS = {
    "student": StudentProfile,
    "teacher": TeacherProfile,
    "moderator": ModeratorProfile,
}


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    date_of_birth = serializers.DateField(write_only=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ["id", "email", "password", "password_confirm", "first_name", "last_name", "date_of_birth", "role", "language"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        date_of_birth = validated_data.pop("date_of_birth")
        validated_data.pop('password_confirm')
        validated_data["role"] = "student"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        StudentProfile.objects.create(user=user, date_of_birth=date_of_birth)
        return user

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role", "status",
            "avatar", "language", "is_blocked", "date_joined", "profile",
        ]
        read_only_fields = ["id", "date_joined"]

    def get_profile(self, obj):
        serializer_class = PROFILE_SERIALIZERS.get(obj.role)
        if not serializer_class:
            return None
        profile_attr = obj.role + "profile"
        if not hasattr(obj, profile_attr):
            return None
        return serializer_class(getattr(obj, profile_attr)).data


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "avatar", "language"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists(): # type: ignore
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class EmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )
