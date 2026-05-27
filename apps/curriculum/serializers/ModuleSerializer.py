from rest_framework import serializers

from apps.curriculum.models import Module

from .LessonSerializer import LessonSerializer
from .TestSerializer import TestSerializer


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    tests = TestSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ["id", "title", "description", "order", "lessons", "tests"]
