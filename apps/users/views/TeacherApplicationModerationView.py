from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.exceptions import ApplicationAlreadyDecidedError
from apps.users.filters import TeacherApplicationFilter
from apps.users.models import TeacherApplication
from apps.users.permissions import IsAdminOrModerator
from apps.users.serializers import TeacherApplicationDecisionSerializer, TeacherApplicationSerializer
from apps.users.services.teacher_application_service import TeacherApplicationService


def _moderator_profile(user):
    return getattr(user, "moderator_profile", None)


@extend_schema(tags=["Users"])
class TeacherApplicationModerationViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /teacher-applications/ and /teacher-applications/{id}/, plus the
    approve/cancel actions, the moderator-facing queue for applications
    submitted through the public "register as teacher" form."""

    queryset = TeacherApplication.objects.select_related("moderator_profile__user").prefetch_related("directions")
    serializer_class = TeacherApplicationSerializer
    permission_classes = [IsAdminOrModerator]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = TeacherApplicationFilter
    ordering_fields = ["submitted_at"]
    ordering = ["-submitted_at"]

    @extend_schema(request=TeacherApplicationDecisionSerializer, responses={200: TeacherApplicationSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        application = self.get_object()
        serializer = TeacherApplicationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            TeacherApplicationService.approve(
                application,
                _moderator_profile(request.user),
                serializer.validated_data["comment"],
            )
        except ApplicationAlreadyDecidedError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(TeacherApplicationSerializer(application).data)

    @extend_schema(request=TeacherApplicationDecisionSerializer, responses={200: TeacherApplicationSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        application = self.get_object()
        serializer = TeacherApplicationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            TeacherApplicationService.cancel(
                application,
                _moderator_profile(request.user),
                serializer.validated_data["comment"],
            )
        except ApplicationAlreadyDecidedError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(TeacherApplicationSerializer(application).data)
