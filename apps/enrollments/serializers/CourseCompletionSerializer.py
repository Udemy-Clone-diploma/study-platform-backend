from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.enrollments.models import CourseCompletion


class CourseCompletionSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()
    certificate_thumbnail_url = serializers.SerializerMethodField()
    certificate_serial = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = CourseCompletion
        fields = [
            "id", "course", "slug",
            "title", "teacher_name", "level",
            "image_url", "progress_percent", "duration_hours",
            "started_at", "completed_at",
            "final_score", "certificate_url", "certificate_thumbnail_url",
            "certificate_serial",
            "paid_amount", "paid_currency", "purchased_at",
        ]
        read_only_fields = fields

    def get_slug(self, obj) -> str | None:
        return obj.course.slug if obj.course_id else None

    def get_duration_hours(self, obj) -> int | None:
        # Not snapshotted at completion time, read live from the course, so
        # null if it was later hard-deleted (course is nullable, see model).
        return obj.course.duration_hours if obj.course_id else None

    def get_image_url(self, obj) -> str | None:
        return self._absolute_url(obj.image_url)

    def get_certificate_url(self, obj) -> str | None:
        return self._absolute_url(obj.certificate_url)

    def get_certificate_thumbnail_url(self, obj) -> str | None:
        return absolute_media_url(obj.certificate_thumbnail, self.context.get("request"))

    def get_certificate_serial(self, obj) -> str | None:
        """The registry serial, so the dashboard can print it next to the
        certificate. Prefetched by the view; None for a revoked certificate or
        a completion that predates the registry backfill."""
        certificate = next(
            (c for c in obj.certificates.all() if c.superseded_by_id is None), None
        )
        return certificate.serial if certificate else None

    def _absolute_url(self, url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("http"):
            return url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
