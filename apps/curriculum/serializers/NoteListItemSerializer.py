from rest_framework import serializers


class NoteListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    content = serializers.CharField()
    updated_at = serializers.DateTimeField()
    lesson_id = serializers.IntegerField(allow_null=True)
    lesson_title = serializers.CharField()
    lesson_order = serializers.IntegerField(allow_null=True)
    course_slug = serializers.CharField()
    course_title = serializers.CharField()
    course_level = serializers.CharField()
    module_title = serializers.CharField()
    is_course_completed = serializers.SerializerMethodField()

    def get_is_course_completed(self, obj) -> bool:
        return obj.course_id in self.context.get("completed_course_ids", set())
