from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.schedule.exceptions import SlotAlreadyBookedError, SlotNotAvailableError
from apps.enrollments.exceptions import (
    CourseNotEnrollableError,
    DuplicateEnrollmentError,
    EnrollmentRoleError,
    InvalidAccessWindowError,
    StudentProfileRequiredError,
)
from apps.enrollments.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
)
from apps.enrollments.services import EnrollmentService
from apps.users.permissions import IsAdmin, IsStudentOrAdmin


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
        serializer = EnrollmentCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        try:
            enrollment = EnrollmentService.create_enrollment(
                serializer.validated_data,
                request.user,
            )
        except EnrollmentRoleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except StudentProfileRequiredError as exc:
            return Response(
                {"student_profile_id": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CourseNotEnrollableError as exc:
            return Response(
                {"course_id": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DuplicateEnrollmentError as exc:
            return Response(
                {"course_id": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SlotNotAvailableError as exc:
            return Response(
                {"schedule_slot_id": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SlotAlreadyBookedError as exc:
            return Response(
                {"schedule_slot_id": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            EnrollmentSerializer(enrollment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        serializer = EnrollmentUpdateSerializer(
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        try:
            enrollment = EnrollmentService.update_enrollment(
                enrollment,
                serializer.validated_data,
            )
        except InvalidAccessWindowError as exc:
            return Response(
                {"access_until": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            EnrollmentSerializer(enrollment, context=self.get_serializer_context()).data,
        )

    def destroy(self, request, *args, **kwargs):
        enrollment = self.get_object()
        EnrollmentService.revoke_enrollment(enrollment)
        return Response(status=status.HTTP_204_NO_CONTENT)
