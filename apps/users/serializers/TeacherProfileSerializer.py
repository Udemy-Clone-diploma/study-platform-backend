from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.users.models import TeacherProfile


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = [
            "id", "bio", "experience", "specialization", "rating",
            "years_experience", "partnerships_count", "signature",
        ]
        read_only_fields = ["rating"]

    def to_representation(self, instance: TeacherProfile) -> dict:
        data = super().to_representation(instance)
        data["signature"] = absolute_media_url(instance.signature, self.context.get("request"))
        return data
