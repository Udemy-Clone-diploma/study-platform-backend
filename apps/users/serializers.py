from rest_framework import serializers

from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile, User


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
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "language"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        profile_model = PROFILE_MODELS.get(user.role)
        if profile_model:
            profile_model.objects.create(user=user)
        return user


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "role", "status",
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
        fields = ["username", "email", "avatar", "language"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
