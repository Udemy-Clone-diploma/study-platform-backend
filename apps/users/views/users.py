from django.db.models import Value
from django.db.models.functions import Concat
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.serializers import MessageSerializer
from apps.users.exceptions import (
    LastAdministratorError,
    ProfileNotAvailableError,
    SelfActionError,
)
from apps.users.filters import UserFilter
from apps.users.models import User
from apps.users.permissions import IsAdmin
from apps.users.serializers import (
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    UserBlockSerializer,
    UserSerializer,
)
from apps.users.services.user_service import UserService


@extend_schema(tags=["Users"])
class UserSearchView(APIView):
    """GET /users/search/ finds users to invite to personal events.

    Not the admin user search: the admin Users table filters via
    GET /users/?search= instead.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = (request.query_params.get("email") or "").strip()
        if len(email) < 3:
            return Response({"detail": "Provide at least 3 characters"}, status=400)

        users = (
            User.objects.filter(email__icontains=email)
            .exclude(
                role__in=(
                    User.RoleChoices.MODERATOR,
                    User.RoleChoices.ADMINISTRATOR,
                )
            )
            .exclude(pk=request.user.pk)[:10]
        )
        data = [
            {
                "id": u.id,
                "email": u.email,
                "name": u.get_full_name() or u.email,
                "role": u.role,
                "avatar": request.build_absolute_uri(u.avatar.url) if u.avatar else None,
            }
            for u in users
        ]
        return Response(data)


@extend_schema(tags=["Users"])
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = UserFilter
    ordering_fields = ["date_joined", "email", "full_name", "first_name", "last_name"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        # The admin list shows deleted users by default (the is_deleted
        # filter narrows to true/false on demand).
        if self.action in ("list", "restore"):
            queryset = User.all_objects.all()
        else:
            queryset = User.objects.all()
        # Backs ?ordering=full_name for the admin table's User column.
        return queryset.annotate(full_name=Concat("first_name", Value(" "), "last_name"))

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        if self.action == "partial_update":
            return AdminUserUpdateSerializer
        return UserSerializer

    def _user_response(self, user, status_code=status.HTTP_200_OK):
        return Response(
            UserSerializer(user, context=self.get_serializer_context()).data,
            status=status_code,
        )

    @extend_schema(responses={201: UserSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        UserService.ensure_profile(user)
        return self._user_response(user, status.HTTP_201_CREATED)

    @extend_schema(responses={200: UserSerializer})
    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # A role change must materialize the new role's profile, or the
        # response (and every later read) serializes profile as null.
        UserService.ensure_profile(user)
        return self._user_response(user)

    @extend_schema(responses={204: None, 400: MessageSerializer})
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        try:
            UserService.soft_delete_user(user, acting_user=request.user)
        except (SelfActionError, LastAdministratorError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={200: UserSerializer})
    @action(detail=True, methods=["patch"], url_path="restore")
    def restore(self, request, pk=None):
        user = self.get_object()
        user = UserService.restore_user(user)
        return self._user_response(user)

    @extend_schema(
        request=UserBlockSerializer,
        responses={200: UserSerializer, 400: MessageSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        user = self.get_object()
        serializer = UserBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = UserService.set_block_status(
                user,
                is_blocked=serializer.validated_data["is_blocked"],
                acting_user=request.user,
            )
        except (SelfActionError, LastAdministratorError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return self._user_response(user)

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

        return self._user_response(user)
