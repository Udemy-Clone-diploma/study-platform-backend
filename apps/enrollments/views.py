from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.enrollments.models import Enrollment
from apps.enrollments.permissions import IsStudentOrAdmin
from apps.enrollments.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
)
from apps.enrollments.services import EnrollmentService
from apps.users.models import User
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Enrollments"])
class EnrollmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Enrollment.objects.select_related(
        "student_profile__user",
        "course",
        "course__teacher_profile__user",
    )
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["access_status", "course", "student_profile"]
    ordering_fields = ["id", "access_granted_at", "access_until"]
    ordering = ["-access_granted_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return queryset.none()

        if user.role in (
            User.RoleChoices.ADMINISTRATOR,
            User.RoleChoices.MODERATOR,
        ):
            return queryset

        if user.role == User.RoleChoices.TEACHER:
            return queryset.filter(course__teacher_profile__user_id=user.id)

        if user.role == User.RoleChoices.STUDENT:
            return queryset.filter(student_profile__user_id=user.id)

        return queryset.none()

    def get_permissions(self):
        if self.action == "create":
            return [IsStudentOrAdmin()]
        if self.action in {"partial_update", "destroy"}:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return EnrollmentCreateSerializer
        if self.action == "partial_update":
            return EnrollmentUpdateSerializer
        return EnrollmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = EnrollmentService.create_enrollment(
            serializer.validated_data,
            request.user,
        )
        return Response(
            EnrollmentSerializer(enrollment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        enrollment = EnrollmentService.update_enrollment(
            enrollment,
            serializer.validated_data,
        )
        return Response(
            EnrollmentSerializer(enrollment, context=self.get_serializer_context()).data
        )

    def destroy(self, request, *args, **kwargs):
        enrollment = self.get_object()
        EnrollmentService.revoke_enrollment(enrollment)
        return Response(status=status.HTTP_204_NO_CONTENT)
