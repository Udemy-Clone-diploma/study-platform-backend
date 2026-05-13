from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsSetPagination
from apps.courses.exceptions import CourseNotFoundError
from apps.courses.serializers import CourseListSerializer
from apps.courses.services import WishlistService
from apps.users.permissions import IsStudent


@extend_schema(tags=["Wishlist"])
class WishlistListView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        summary="List the current student's wishlisted courses",
        responses={200: CourseListSerializer(many=True)},
    )
    def get(self, request):
        courses = WishlistService.get_wishlisted_courses(request.user.student_profile)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(courses, request)
        data = WishlistService.serialize_courses(page, request)
        return paginator.get_paginated_response(data)


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
