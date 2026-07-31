from rest_framework import serializers

from apps.curriculum.models import Module

from .PublicCourseLessonSerializer import PublicCourseLessonSerializer


class PublicCourseModuleSerializer(serializers.ModelSerializer):
    lessons = PublicCourseLessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ["id", "title", "description", "order", "lessons"]
        read_only_fields = fields
