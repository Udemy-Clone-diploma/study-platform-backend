from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.users.models import User
from apps.users.serializers import PublicUserSerializer


@extend_schema(tags=["Users"])
class PublicUserProfileView(RetrieveAPIView):
    """Safe profile details visible to other authenticated users."""

    permission_classes = [IsAuthenticated]
    serializer_class = PublicUserSerializer
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return User.objects.select_related(
            "student_profile",
            "teacher_profile",
            "moderator_profile",
        )
