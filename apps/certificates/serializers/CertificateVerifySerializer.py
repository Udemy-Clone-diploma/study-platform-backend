from rest_framework import serializers

from apps.certificates.models import Certificate


class CertificateVerifySerializer(serializers.ModelSerializer):
    """The public payload.

    Deliberately slim: no student email or id, no course id, no issuer, and no
    revoke reason. A third party needs to know that a certificate exists and
    whether it still stands, not why it was withdrawn.
    """

    student_name = serializers.CharField(read_only=True)
    superseded_by_serial = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "serial",
            "status",
            "student_name",
            "course_title",
            "issued_at",
            "revoked_at",
            "superseded_by_serial",
        ]
        read_only_fields = fields

    def get_superseded_by_serial(self, obj: Certificate) -> str | None:
        return obj.superseded_by.serial if obj.superseded_by_id else None
