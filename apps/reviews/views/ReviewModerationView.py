from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.exceptions import (
    ReviewAlreadyAssignedError,
    ReviewNotAssignedToModeratorError,
    ReviewsError,
)
from apps.reviews.models import Review
from apps.reviews.serializers import ModeratorReviewSerializer
from apps.reviews.services import ReviewService
from apps.users.permissions import IsAdminOrModerator


def _moderator_profile(user):
    return getattr(user, "moderator_profile", None)


@extend_schema(tags=["Reviews"])
class ReviewsUnassignedModerationView(ListAPIView):
    """GET /reviews/moderation/unassigned/: reported reviews no moderator has claimed yet."""

    serializer_class = ModeratorReviewSerializer
    permission_classes = [IsAdminOrModerator]

    def get_queryset(self):
        return ReviewService.get_unassigned_reported_queryset()


@extend_schema(tags=["Reviews"])
class ReviewsMyModerationView(ListAPIView):
    """GET /reviews/moderation/mine/: reported reviews claimed by the current moderator."""

    serializer_class = ModeratorReviewSerializer
    permission_classes = [IsAdminOrModerator]

    def get_queryset(self):
        return ReviewService.get_my_reported_queryset(_moderator_profile(self.request.user))


@extend_schema(tags=["Reviews"])
class ReviewAssignModeratorView(APIView):
    """POST /reviews/{id}/assign-moderator/: claim a reported review for moderation."""

    permission_classes = [IsAuthenticated, IsAdminOrModerator]

    def post(self, request, pk):
        review = get_object_or_404(Review.all_objects, pk=pk)
        try:
            ReviewService.assign_moderator_self(review, _moderator_profile(request.user))
        except ReviewAlreadyAssignedError:
            return Response(
                {"detail": "This review already has a moderator assigned."},
                status=status.HTTP_409_CONFLICT,
            )
        except ReviewsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"detail": "Moderator assigned."})


@extend_schema(tags=["Reviews"])
class ReviewApproveView(APIView):
    """POST /reviews/{id}/approve/: dismiss the reports; the review stays live."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, pk):
        review = get_object_or_404(Review.all_objects, pk=pk)
        try:
            ReviewService.approve_reported_review(review, _moderator_profile(request.user))
        except ReviewNotAssignedToModeratorError:
            return Response(
                {"detail": "Assign yourself to this review before moderating it."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Reviews"])
class ReviewRejectView(APIView):
    """POST /reviews/{id}/reject/: uphold the reports; hide the review from public view."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, pk):
        review = get_object_or_404(Review.all_objects, pk=pk)
        try:
            ReviewService.reject_reported_review(review, _moderator_profile(request.user))
        except ReviewNotAssignedToModeratorError:
            return Response(
                {"detail": "Assign yourself to this review before moderating it."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
