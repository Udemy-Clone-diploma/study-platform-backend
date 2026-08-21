from rest_framework import serializers

from apps.common.sanitize import sanitize_html
from apps.curriculum.models import LessonItem, Test


class LessonItemCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonItem
        fields = [
            "item_type",
            "body_html",
            "video",
            "video_url",
            "duration_minutes",
            "test",
        ]
        extra_kwargs = {
            "body_html": {"required": False},
            "video": {"required": False},
            "video_url": {"required": False},
            "duration_minutes": {"required": False},
            "test": {"required": False},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict the test FK to tests belonging to the same course so a teacher
        # cannot attach another course's test to their lesson item.
        lesson = self.context.get("lesson")
        if lesson is not None:
            self.fields["test"].queryset = Test.objects.filter(
                module__course_id=lesson.module.course_id
            )

    def validate_body_html(self, value):
        return sanitize_html(value)

    def validate(self, attrs):
        item_type = attrs.get("item_type") or getattr(self.instance, "item_type", None)
        if item_type == LessonItem.ItemType.TEST:
            has_test = attrs.get("test") or (self.instance and self.instance.test_id)
            if not has_test:
                raise serializers.ValidationError({"test": "A test must be provided for a TEST item."})
        return attrs

    def save(self, **kwargs):
        video = self.validated_data.get("video")
        if video and hasattr(video, "name"):
            kwargs["original_video_name"] = video.name
        return super().save(**kwargs)
