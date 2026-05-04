from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.exceptions import ProfileNotAvailableError
from apps.users.models import User
from apps.users.permissions import IsAdmin
from apps.users.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.users.services.user_service import UserService


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [IsAdmin]

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
        UserService.soft_delete_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        user = self.get_object()
        is_blocked = request.data.get("is_blocked", True)

        user = UserService.set_block_status(user, is_blocked=is_blocked)

        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["patch"], url_path="profile")
    def profile(self, request, pk=None):
        user = self.get_object()

        try:
            user = UserService.update_profile(user, request.data)
        except ProfileNotAvailableError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(UserSerializer(user).data)
