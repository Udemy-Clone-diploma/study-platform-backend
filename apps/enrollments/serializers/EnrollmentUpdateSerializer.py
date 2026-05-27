from rest_framework import serializers

from apps.enrollments.models import Enrollment


class EnrollmentUpdateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )
    access_status = serializers.ChoiceField(
        choices=Enrollment.AccessStatusChoices.choices,
        required=False,
    )
    access_until = serializers.DateTimeField(required=False, allow_null=True)
