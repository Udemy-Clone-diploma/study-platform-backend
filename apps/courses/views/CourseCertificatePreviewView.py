from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.enrollments.services import CertificateService

from ._course_scoped import ensure_can_modify_course, get_course_for_request


@extend_schema(tags=["Courses"])
class CourseCertificatePreviewView(APIView):
    """Live certificate preview for the course owner (teacher) or an admin,
    always rendered from the course's current data, never persisted."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        course = get_course_for_request(self, slug)
        ensure_can_modify_course(request.user, course)

        if not course.with_certificate:
            return Response(
                {"detail": "This course does not offer a certificate."},
                status=status.HTTP_409_CONFLICT,
            )

        pdf = CertificateService.render_preview_pdf(course)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="certificate-preview-{course.slug}.pdf"'
        response["Content-Length"] = str(len(pdf))
        return response
