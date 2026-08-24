from rest_framework import serializers

from apps.reviews.models import Review
from apps.reviews.serializers.ReviewSerializer import ReviewStudentSerializer


class ReviewCourseSerializer(serializers.Serializer):
    slug = serializers.CharField()
    title = serializers.CharField()


class TopReviewSerializer(serializers.ModelSerializer):
    """Cross-course review for platform-wide "top reviews" surfaces (e.g. the homepage)."""

    student = ReviewStudentSerializer(read_only=True)
    course = ReviewCourseSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "student", "course", "rating", "text", "created_at"]
