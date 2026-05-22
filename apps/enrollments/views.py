from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.enrollments.permissions import IsStudentOrAdmin
from apps.enrollments.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
)
from apps.enrollments.services import EnrollmentService
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
    queryset = EnrollmentService.get_base_queryset()
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["access_status", "course", "student_profile"]
    ordering_fields = ["id", "access_granted_at", "access_until"]
    ordering = ["-access_granted_at"]

    def get_queryset(self):
        return EnrollmentService.get_visible_enrollments_queryset(
            self.request.user,
            super().get_queryset(),
        )

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
        data = EnrollmentService.create_enrollment_from_data(
            request.data,
            request.user,
            self.get_serializer_context(),
        )
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        data = EnrollmentService.update_enrollment_from_data(
            enrollment,
            request.data,
            self.get_serializer_context(),
        )
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        enrollment = self.get_object()
        EnrollmentService.revoke_enrollment(enrollment)
        return Response(status=status.HTTP_204_NO_CONTENT)
