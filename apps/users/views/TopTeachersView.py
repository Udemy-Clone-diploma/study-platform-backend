from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.users.constants import DEFAULT_TOP_TEACHERS_LIMIT
from apps.users.serializers import TopTeacherSerializer
from apps.users.services.user_service import UserService


class TopTeachersView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Users"],
        parameters=[OpenApiParameter("limit", int, description="Max number of teachers to return.")],
        responses={200: TopTeacherSerializer(many=True), 400: {"type": "object"}},
    )
    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_TOP_TEACHERS_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        teachers = UserService.get_top_teachers(
            limit=limit,
            context={"request": request},
        )
        return Response(teachers)
