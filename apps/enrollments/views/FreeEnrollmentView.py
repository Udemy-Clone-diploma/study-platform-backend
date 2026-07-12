from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.exceptions import (
    CourseNotEnrollableError,
    EnrollmentRoleError,
    FreeEnrollmentUnavailableError,
    StudentProfileRequiredError,
)
from apps.enrollments.serializers import EnrollmentSerializer
from apps.enrollments.services import EnrollmentService
from apps.users.permissions import IsStudent


@extend_schema(tags=["Enrollments"])
class FreeEnrollmentView(APIView):
    """Grant access to a published course that has a zero-price plan."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(request=None, responses={200: EnrollmentSerializer, 201: EnrollmentSerializer})
    def post(self, request, slug: str):
        course = get_object_or_404(
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED),
            slug=slug,
        )
        try:
            enrollment, created = EnrollmentService.enroll_in_free_course(
                request.user,
                course,
                delivery_format_id=request.data.get("delivery_format_id"),
                pricing_plan_id=request.data.get("pricing_plan_id"),
                cohort_id=request.data.get("cohort_id"),
                schedule_slot_ids=request.data.get("schedule_slot_ids"),
            )
        except (CourseNotEnrollableError, FreeEnrollmentUnavailableError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except StudentProfileRequiredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except EnrollmentRoleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            EnrollmentSerializer(enrollment, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
