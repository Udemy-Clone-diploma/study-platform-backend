from django.db.models import Count, Q
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import IntegerField

from apps.certificates.exceptions import (
    CertificateRenderError,
    CertificatesError,
    StudentNotEnrolledError,
)
from apps.certificates.filters import CertificateFilter
from apps.certificates.models import Certificate
from apps.certificates.serializers import (
    CertificateIssueSerializer,
    CertificateOwnerVisibilitySerializer,
    CertificateReasonSerializer,
    CertificateSerializer,
    CertificateVisibilitySerializer,
)
from apps.certificates.services import CertificateRegistryService
from apps.users.models import User
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Certificates"])
class CertificateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """The admin certificate registry. No delete route by design: a certificate
    records something asserted to a third party, so it is revoked, never erased."""

    serializer_class = CertificateSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CertificateFilter
    ordering_fields = ["issued_at", "serial", "student_name", "course_title"]
    ordering = ["-issued_at"]

    def get_queryset(self):
        queryset = Certificate.objects.select_related(
            "student_profile__user",
            "course",
            "completion",
            "issued_by",
            "revoked_by",
            "restored_by",
            "superseded_by",
        )
        if self.action == "visibility" and not self._is_admin():
            # A student may only touch their own. Anything else 404s rather than
            # 403, so the endpoint never confirms that a serial exists.
            return queryset.filter(student_profile__user=self.request.user)
        return queryset

    def get_permissions(self):
        # The one action a student may reach: their own certificate's visibility.
        if self.action == "visibility":
            return [IsAuthenticated()]
        return super().get_permissions()

    def _is_admin(self) -> bool:
        return getattr(self.request.user, "role", None) == User.RoleChoices.ADMINISTRATOR

    @extend_schema(
        request=CertificateIssueSerializer,
        responses={201: CertificateSerializer},
        summary="Issue a certificate by hand (administrators only)",
    )
    def create(self, request, *args, **kwargs):
        serializer = CertificateIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            certificate = CertificateRegistryService.issue_manually(
                student_user=serializer.validated_data["student"],
                course=serializer.validated_data["course"],
                reason=serializer.validated_data["reason"],
                issued_by=request.user,
            )
        except (StudentNotEnrolledError, CertificateRenderError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except CertificatesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return self._certificate_response(certificate, status.HTTP_201_CREATED)

    @extend_schema(
        request=CertificateVisibilitySerializer,
        responses={200: CertificateSerializer},
        summary="Set whether a certificate answers to public verification",
    )
    def partial_update(self, request, *args, **kwargs):
        serializer = CertificateVisibilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        certificate = CertificateRegistryService.set_visibility(
            certificate=self.get_object(),
            is_public=serializer.validated_data["is_public"],
        )
        return self._certificate_response(certificate, status.HTTP_200_OK)

    @extend_schema(
        request=CertificateVisibilitySerializer,
        responses={200: CertificateOwnerVisibilitySerializer},
        summary="Opt your own certificate in or out of public verification",
    )
    @action(detail=True, methods=["patch"], url_path="visibility")
    def visibility(self, request, *args, **kwargs):
        serializer = CertificateVisibilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        certificate = CertificateRegistryService.set_visibility(
            certificate=self.get_object(),
            is_public=serializer.validated_data["is_public"],
        )
        return Response(CertificateOwnerVisibilitySerializer(certificate).data)

    @extend_schema(
        request=CertificateReasonSerializer,
        responses={201: CertificateSerializer},
        summary="Re-issue a certificate after a correction",
    )
    @action(detail=True, methods=["post"], url_path="reissue")
    def reissue(self, request, *args, **kwargs):
        reason = self._reason(request)
        try:
            replacement = CertificateRegistryService.reissue(
                certificate=self.get_object(),
                reason=reason,
                issued_by=request.user,
            )
        except CertificateRenderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except CertificatesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return self._certificate_response(replacement, status.HTTP_201_CREATED)

    @extend_schema(
        request=CertificateReasonSerializer,
        responses={200: CertificateSerializer},
        summary="Revoke a certificate",
    )
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, *args, **kwargs):
        reason = self._reason(request)
        try:
            certificate = CertificateRegistryService.revoke(
                certificate=self.get_object(),
                reason=reason,
                revoked_by=request.user,
            )
        except CertificatesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return self._certificate_response(certificate, status.HTTP_200_OK)

    @extend_schema(
        request=CertificateReasonSerializer,
        responses={200: CertificateSerializer},
        summary="Undo a revoke",
    )
    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, *args, **kwargs):
        reason = self._reason(request)
        try:
            certificate = CertificateRegistryService.restore(
                certificate=self.get_object(),
                reason=reason,
                restored_by=request.user,
            )
        except CertificatesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return self._certificate_response(certificate, status.HTTP_200_OK)

    @extend_schema(
        responses={
            200: inline_serializer(
                name="CertificateCounts",
                fields={
                    "total": IntegerField(),
                    "valid": IntegerField(),
                    "revoked": IntegerField(),
                },
            )
        },
        summary="Per-status certificate counts for the filter tabs",
    )
    @action(detail=False, methods=["get"], url_path="counts")
    def counts(self, request, *args, **kwargs):
        # `status` is dropped from the filters on purpose: a tab's count must
        # not change when that tab is the one selected.
        params = request.query_params.copy()
        params.pop("status", None)
        queryset = CertificateFilter(params, queryset=self.get_queryset(), request=request).qs
        statuses = Certificate.StatusChoices
        return Response(
            queryset.aggregate(
                total=Count("id"),
                valid=Count("id", filter=Q(status=statuses.VALID)),
                revoked=Count("id", filter=Q(status=statuses.REVOKED)),
            )
        )

    @extend_schema(summary="Download the certificate PDF")
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, *args, **kwargs):
        certificate = self.get_object()
        pdf_file = certificate.pdf_file
        if not pdf_file:
            return Response(
                {"detail": "This certificate has no PDF on file. Re-issue it to generate one."},
                status=status.HTTP_409_CONFLICT,
            )

        pdf_file.open("rb")
        try:
            pdf = pdf_file.read()
        finally:
            pdf_file.close()

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{certificate.serial}.pdf"'
        response["Content-Length"] = str(len(pdf))
        return response

    def _reason(self, request) -> str:
        serializer = CertificateReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["reason"]

    def _certificate_response(self, certificate: Certificate, status_code: int) -> Response:
        return Response(
            self.get_serializer(certificate).data,
            status=status_code,
        )
