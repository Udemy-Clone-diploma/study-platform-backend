from rest_framework import serializers

from apps.courses.models import Course
from apps.users.models import User

MIN_REASON_LENGTH = 5


class CertificateIssueSerializer(serializers.Serializer):
    """Body of POST /certificates/. `student` is a User id, not a StudentProfile id."""

    student = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.RoleChoices.STUDENT),
    )
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    # Required and non-blank: this is the audit trail for a human overriding the
    # automatic passing-score rule.
    reason = serializers.CharField(min_length=MIN_REASON_LENGTH, trim_whitespace=True)


class CertificateReasonSerializer(serializers.Serializer):
    """Body of the re-issue, revoke and restore actions."""

    reason = serializers.CharField(min_length=MIN_REASON_LENGTH, trim_whitespace=True)


class CertificateVisibilitySerializer(serializers.Serializer):
    """Body of the visibility toggles. `is_public` is the only mutable field on
    a certificate: everything else is a record of what was asserted."""

    is_public = serializers.BooleanField()


class CertificateOwnerVisibilitySerializer(serializers.Serializer):
    """What a student gets back for their own certificate. Deliberately omits
    issue_note and revoke_reason, which are internal admin notes."""

    id = serializers.IntegerField(read_only=True)
    serial = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(read_only=True)
