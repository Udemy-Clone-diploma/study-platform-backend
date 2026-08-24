from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.chat.models import ChatParticipant
from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.users.cache import public_user_profile_cache_key
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

    def _shares_active_chat(self, target_user_id: int) -> bool:
        return ChatParticipant.objects.filter(
            user=self.request.user,
            left_at__isnull=True,
            chat__is_deleted=False,
            chat__participants__user_id=target_user_id,
            chat__participants__left_at__isnull=True,
        ).exists()

    def retrieve(self, request, *args, **kwargs):
        target_user_id = kwargs[self.lookup_url_kwarg]
        if request.user.pk == target_user_id or not self._shares_active_chat(target_user_id):
            return super().retrieve(request, *args, **kwargs)

        key = public_user_profile_cache_key(request, target_user_id)
        data = cache_get_or_set(
            key,
            lambda: self.get_serializer(self.get_object()).data,
            timeout=jittered_cache_timeout(
                settings.PUBLIC_USER_PROFILE_CACHE_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(data)
