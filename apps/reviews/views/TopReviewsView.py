from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.reviews.constants import DEFAULT_TOP_REVIEWS_LIMIT
from apps.reviews.serializers import TopReviewSerializer
from apps.reviews.services import ReviewService


@extend_schema(tags=["Reviews"])
class TopReviewsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter("limit", int, description="Max number of reviews to return.")],
        responses={200: TopReviewSerializer(many=True), 400: {"type": "object"}},
    )
    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_TOP_REVIEWS_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        reviews = ReviewService.get_top_reviews(limit=limit, context={"request": request})
        return Response(reviews)