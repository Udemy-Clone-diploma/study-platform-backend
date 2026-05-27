from rest_framework import serializers

from apps.courses.models import Lesson


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ["title", "content", "video", "duration_minutes", "min_score"]
        extra_kwargs = {
            "content": {"required": False},
            "video": {"required": False},
            "duration_minutes": {"required": False},
            "min_score": {"required": False},
        }
