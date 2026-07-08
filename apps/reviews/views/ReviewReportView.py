from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.exceptions import AlreadyReportedError, CannotReportOwnReviewError
from apps.reviews.models import Review
from apps.reviews.services import ReviewService


class _ReviewReportSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


@extend_schema(tags=["Reviews"])
class ReviewReportView(APIView):
    """POST /reviews/{id}/report/ — flag a review for moderator attention."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        serializer = _ReviewReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ReviewService.report_review(request.user, review, reason=serializer.validated_data["reason"])
        except CannotReportOwnReviewError:
            return Response({"detail": "You cannot report your own review."}, status=status.HTTP_403_FORBIDDEN)
        except AlreadyReportedError:
            return Response({"detail": "You have already reported this review."}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_201_CREATED)
