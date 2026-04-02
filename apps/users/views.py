from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import User
from apps.users.serializers import (
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

    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        user = self.get_object()
        is_blocked = request.data.get("is_blocked", True)
        user.is_blocked = is_blocked
        user.status = "inactive" if is_blocked else "active"
        user.save()
        return Response(UserSerializer(user).data)
