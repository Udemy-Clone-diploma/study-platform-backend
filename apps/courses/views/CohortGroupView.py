from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Cohort, CohortMember
from apps.courses.serializers.CohortGroupSerializer import CohortMemberSerializer, EnrolledStudentSerializer
from apps.enrollments.models import Enrollment

from ._course_scoped import ensure_can_modify_course, get_course_for_request


@extend_schema(tags=["Cohort Members"])
class CohortMemberListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        cohort = get_object_or_404(Cohort, pk=self.kwargs["cohort_id"], course=course)

        enrollment_id = request.data.get("enrollment_id")
        if not enrollment_id:
            return Response(
                {"enrollment_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment = get_object_or_404(
            Enrollment.objects.filter(course=course),
            pk=enrollment_id,
        )

        if CohortMember.objects.filter(cohort=cohort, enrollment=enrollment).exists():
            return Response(
                {"detail": "Student is already in this cohort."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if CohortMember.objects.filter(cohort__course=course, enrollment=enrollment).exists():
            return Response(
                {"detail": "Student is already assigned to another cohort of this course."},
                status=status.HTTP_409_CONFLICT,
            )

        member = CohortMember.objects.create(cohort=cohort, enrollment=enrollment)
        return Response(CohortMemberSerializer(member, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Cohort Members"])
class CohortMemberDetailView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "member_id"

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        cohort = get_object_or_404(Cohort, pk=self.kwargs["cohort_id"], course=course)
        return CohortMember.objects.filter(cohort=cohort)

    def destroy(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        member = self.get_object()
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Cohort Members"])
class CourseEnrolledStudentsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        qs = Enrollment.objects.filter(course=course).select_related(
            "student_profile__user",
            "delivery_format",
            "course",
        )
        format_id = request.query_params.get("format_id")
        if format_id:
            qs = qs.filter(delivery_format_id=format_id)
        return Response(EnrolledStudentSerializer(qs, many=True, context={"request": request}).data)
