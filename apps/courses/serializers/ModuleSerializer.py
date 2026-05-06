from rest_framework import serializers

from apps.courses.models import Module

from .LessonSerializer import LessonSerializer


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ["id", "title", "description", "order", "lessons"]
