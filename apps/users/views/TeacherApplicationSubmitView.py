from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.users.serializers import TeacherApplicationCreateSerializer, TeacherApplicationSerializer
from apps.users.services.teacher_application_service import TeacherApplicationService


@extend_schema(tags=["Users"])
class TeacherApplicationSubmitView(APIView):
    """POST /teacher-applications/submit/ — public submission of a teacher application."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_application"

    @extend_schema(request=TeacherApplicationCreateSerializer, responses={201: TeacherApplicationSerializer})
    def post(self, request):
        serializer = TeacherApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = TeacherApplicationService.submit(serializer.validated_data)
        return Response(
            TeacherApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Users"])
class TeacherApplicationEmailCheckView(APIView):
    """GET /teacher-applications/check-email/?email=... — lets the public form validate

    the email as soon as the applicant enters it, instead of only at final submit."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "teacher_application_check"

    @extend_schema(
        responses={
            200: inline_serializer(
                "TeacherApplicationEmailCheckSerializer",
                {
                    "available": drf_serializers.BooleanField(),
                    "detail": drf_serializers.CharField(required=False),
                },
            ),
        }
    )
    def get(self, request):
        email = (request.query_params.get("email") or "").strip()
        if not email:
            return Response({"available": True})

        conflict = TeacherApplicationService.email_conflict(email)
        if conflict:
            return Response({"available": False, "detail": conflict})
        return Response({"available": True})
