from rest_framework import serializers

from apps.curriculum.models import LessonItem


class LessonItemCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonItem
        fields = [
            "item_type",
            "content",
            "body_html",
            "video",
            "video_url",
            "duration_minutes",
            "test",
        ]
        extra_kwargs = {
            "content": {"required": False},
            "body_html": {"required": False},
            "video": {"required": False},
            "video_url": {"required": False},
            "duration_minutes": {"required": False},
            "test": {"required": False},
        }

    def validate(self, attrs):
        item_type = attrs.get("item_type") or getattr(self.instance, "item_type", None)
        if item_type == LessonItem.ItemType.TEST:
            has_test = attrs.get("test") or (self.instance and self.instance.test_id)
            if not has_test:
                raise serializers.ValidationError({"test": "Для TEST-елементу потрібно вказати test."})
        return attrs

    def save(self, **kwargs):
        video = self.validated_data.get("video")
        if video and hasattr(video, "name"):
            kwargs["original_video_name"] = video.name
        return super().save(**kwargs)
