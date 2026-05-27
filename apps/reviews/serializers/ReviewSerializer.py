from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.reviews.models import Review


class ReviewStudentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="get_full_name")
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class ReviewSerializer(serializers.ModelSerializer):
    student = ReviewStudentSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "student", "rating", "text", "created_at"]
        read_only_fields = ["id", "student", "created_at"]
