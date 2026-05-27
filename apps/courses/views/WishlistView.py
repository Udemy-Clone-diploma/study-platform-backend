from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import CourseNotFoundError
from apps.courses.serializers import CourseListSerializer
from apps.courses.services import WishlistService
from apps.users.permissions import IsStudent


@extend_schema(
    tags=["Wishlist"],
    summary="List the current student's wishlisted courses",
)
class WishlistListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = CourseListSerializer

    def get_queryset(self):
        return WishlistService.get_wishlisted_courses(self.request.user.student_profile)


@extend_schema(tags=["Wishlist"])
class WishlistToggleView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        summary="Toggle a course in the student's wishlist",
        responses={200: {"type": "object", "properties": {"is_wishlisted": {"type": "boolean"}}}},
    )
    def post(self, request, slug):
        try:
            is_wishlisted = WishlistService.toggle(request.user.student_profile, slug)
        except CourseNotFoundError:
            return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"is_wishlisted": is_wishlisted})
