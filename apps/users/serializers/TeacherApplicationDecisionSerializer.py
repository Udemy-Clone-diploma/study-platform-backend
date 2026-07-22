from rest_framework import serializers


class TeacherApplicationDecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")
