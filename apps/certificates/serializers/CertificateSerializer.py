from rest_framework import serializers

from apps.certificates.models import Certificate
from apps.common.files import absolute_media_url


class CertificateStudentSerializer(serializers.Serializer):
    """`id` is the student's User id, matching the `user` filter on /payments/
    and the ids returned by /users/."""

    id = serializers.IntegerField(source="user_id", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.user.avatar, self.context.get("request"))


class CertificateCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)


class CertificateIssuerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)


class CertificateSerializer(serializers.ModelSerializer):
    student = CertificateStudentSerializer(source="student_profile", read_only=True)
    course = CertificateCourseSerializer(read_only=True)
    issued_by = CertificateIssuerSerializer(read_only=True)
    revoked_by = CertificateIssuerSerializer(read_only=True)
    restored_by = CertificateIssuerSerializer(read_only=True)
    superseded_by = serializers.IntegerField(source="superseded_by_id", read_only=True)
    certificate_url = serializers.SerializerMethodField()
    certificate_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "serial",
            "public_uuid",
            "student",
            "course",
            "course_title",
            "status",
            "issued_at",
            "issued_by",
            "issue_reason",
            "issue_note",
            "final_score",
            "revoked_at",
            "revoked_by",
            "revoke_reason",
            "restored_at",
            "restored_by",
            "restore_reason",
            "completion_reverted",
            "superseded_by",
            "is_public",
            "certificate_url",
            "certificate_thumbnail_url",
        ]
        read_only_fields = fields

    def get_certificate_url(self, obj: Certificate) -> str | None:
        return absolute_media_url(obj.pdf_file, self.context.get("request"))

    def get_certificate_thumbnail_url(self, obj: Certificate) -> str | None:
        return absolute_media_url(obj.thumbnail_file, self.context.get("request"))
