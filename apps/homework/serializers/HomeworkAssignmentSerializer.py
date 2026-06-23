from rest_framework import serializers

from apps.curriculum.models import Lesson, Module
from apps.homework.models import HomeworkAssignment


class HomeworkAssignmentSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(source="course.id", read_only=True)
    lesson = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.all(),
        allow_null=True,
        required=False,
    )
    module = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = HomeworkAssignment
        fields = [
            "id",
            "course_id",
            "module",
            "lesson",
            "title",
            "description",
            "due_at",
            "max_score",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "course_id", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "max_score": {"min_value": 1},
        }

    def validate(self, attrs: dict) -> dict:
        course = self.context["course"]
        module: Module | None = attrs.get("module")
        lesson: Lesson | None = attrs.get("lesson")
        errors = {}

        if module is not None and module.course_id != course.id:
            errors["module"] = "The module must belong to the selected course."

        if lesson is not None:
            if lesson.module.course_id != course.id:
                errors["lesson"] = "The lesson must belong to the selected course."
            elif module is not None and lesson.module_id != module.id:
                errors["lesson"] = "The lesson must belong to the selected module."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
