from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.certificates.exceptions import CertificateNotFoundError
from apps.certificates.serializers import CertificateVerifySerializer
from apps.certificates.services import CertificateRegistryService


@extend_schema(tags=["Certificates"])
class CertificateVerifyView(APIView):
    """GET /certificates/verify/<lookup>/ -- public certificate check.

    Unauthenticated by design: this is what an employer hits. Throttled per IP
    because it takes a short identifier and answers truthfully, which without a
    limit makes it an enumeration oracle for the whole registry.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "certificate_verify"

    @extend_schema(
        responses={200: CertificateVerifySerializer},
        summary="Verify a certificate by serial or public UUID (public)",
    )
    def get(self, request, lookup, *args, **kwargs):
        try:
            certificate = CertificateRegistryService.verify(lookup)
        except CertificateNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(CertificateVerifySerializer(certificate).data)
