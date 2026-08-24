from rest_framework import serializers

from apps.common.files import absolute_media_url


class MaterialDocumentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField(source="original_name")
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str | None:
        return absolute_media_url(obj.file, self.context.get("request"))


class MaterialsLessonSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField(source="id")
    lesson_title = serializers.CharField(source="title")
    # Most recent material upload date, not the lesson's own created_at:
    # lessons are typically authored in one batch, so their own timestamp
    # says nothing about when materials were actually added to them.
    lesson_date = serializers.SerializerMethodField()
    module_order = serializers.IntegerField(source="module.order")
    module_title = serializers.CharField(source="module.title")
    course_slug = serializers.CharField(source="module.course.slug")
    course_title = serializers.CharField(source="module.course.title")
    materials = serializers.SerializerMethodField()

    def get_lesson_date(self, obj):
        documents = list(obj.documents.all())
        if not documents:
            return obj.created_at
        return max(document.created_at for document in documents)

    def get_materials(self, obj) -> list:
        documents = obj.documents.all()
        return MaterialDocumentSerializer(documents, many=True, context=self.context).data
