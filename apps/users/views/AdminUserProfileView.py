from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from apps.users.permissions import IsAdminOrModeratorOrTeacher
from apps.users.services.admin_profile_service import AdminProfileService


@extend_schema(tags=["Users"], summary="Staff profile with moderation and platform data")
class AdminUserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrModeratorOrTeacher]

    def get(self, request, user_id: int):
        user = get_object_or_404(
            User.all_objects.select_related(
                "student_profile",
                "teacher_profile",
                "moderator_profile",
            ),
            pk=user_id,
        )
        return Response(AdminProfileService.build(user, request))
