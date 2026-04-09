from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import User
from apps.users.serializers import (
    PROFILE_MODELS,
    PROFILE_SERIALIZERS,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserRegistrationSerializer
        if self.action == "partial_update":
            return UserUpdateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_deleted = True
        user.status = "inactive"
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        user = self.get_object()
        is_blocked = request.data.get("is_blocked", True)
        user.is_blocked = is_blocked
        user.status = "inactive" if is_blocked else "active"
        user.save()
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["patch"], url_path="profile")
    def profile(self, request, pk=None):
        user = self.get_object()
        serializer_class = PROFILE_SERIALIZERS.get(user.role)
        profile_model = PROFILE_MODELS.get(user.role)

        if not serializer_class or not profile_model:
            return Response(
                {"detail": "Profile is not available for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile, _ = profile_model.objects.get_or_create(user=user)
        serializer = serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user).data)
