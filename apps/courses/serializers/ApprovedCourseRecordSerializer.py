from rest_framework import serializers

from apps.courses.models import ApprovedCourseRecord


class ApprovedCourseRecordSerializer(serializers.ModelSerializer):
    course_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ApprovedCourseRecord
        fields = [
            "id",
            "course_slug",
            "course_title",
            "course_image_url",
            "course_category",
            "course_level",
            "changed_fields",
            "approved_at",
        ]

    def get_course_image_url(self, obj) -> str | None:
        if not obj.course_image_url:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.course_image_url)
        return obj.course_image_url
