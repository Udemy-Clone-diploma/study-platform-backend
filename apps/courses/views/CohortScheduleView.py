from datetime import time as time_type

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import InvalidScheduleTimeError, TeacherScheduleConflictError
from apps.courses.models import Cohort, CohortSchedule
from apps.courses.serializers.CohortScheduleSerializer import (
    CohortScheduleSerializer,
    CohortScheduleWriteSerializer,
)
from apps.courses.services import ScheduleService

from ._course_scoped import ensure_can_modify_course, get_course_for_request


def _get_cohort(view, slug: str, cohort_id: int) -> Cohort:
    course = get_course_for_request(view, slug)
    try:
        return Cohort.objects.get(pk=cohort_id, course=course)
    except Cohort.DoesNotExist:
        raise NotFound("Cohort not found.")


def _get_cohort_schedule(cohort: Cohort, schedule_id: int) -> CohortSchedule:
    try:
        return CohortSchedule.objects.get(pk=schedule_id, cohort=cohort)
    except CohortSchedule.DoesNotExist:
        raise NotFound("Cohort schedule not found.")


@extend_schema(tags=["Schedule"])
class CohortScheduleListCreateView(APIView):
    """
    GET  – list all schedules for a cohort (public).
    POST – add a session to a cohort's weekly schedule (teacher / admin only).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, slug, cohort_id):
        cohort    = _get_cohort(self, slug, cohort_id)
        schedules = CohortSchedule.objects.filter(cohort=cohort)
        return Response(CohortScheduleSerializer(schedules, many=True).data)

    def post(self, request, slug, cohort_id):
        cohort = _get_cohort(self, slug, cohort_id)
        ensure_can_modify_course(request.user, cohort.course)

        serializer = CohortScheduleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            schedule = ScheduleService.create_cohort_schedule(cohort, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            CohortScheduleSerializer(schedule).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Schedule"])
class CohortScheduleDetailView(APIView):
    """
    GET    – retrieve a single cohort schedule entry (public).
    PATCH  – update day/time (teacher / admin only).
    DELETE – remove (teacher / admin only).
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, slug, cohort_id, schedule_id):
        cohort   = _get_cohort(self, slug, cohort_id)
        schedule = _get_cohort_schedule(cohort, schedule_id)
        return Response(CohortScheduleSerializer(schedule).data)

    def patch(self, request, slug, cohort_id, schedule_id):
        cohort   = _get_cohort(self, slug, cohort_id)
        ensure_can_modify_course(request.user, cohort.course)
        schedule = _get_cohort_schedule(cohort, schedule_id)

        serializer = CohortScheduleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            schedule = ScheduleService.update_cohort_schedule(schedule, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(CohortScheduleSerializer(schedule).data)

    def delete(self, request, slug, cohort_id, schedule_id):
        cohort   = _get_cohort(self, slug, cohort_id)
        ensure_can_modify_course(request.user, cohort.course)
        schedule = _get_cohort_schedule(cohort, schedule_id)
        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Schedule"])
class CohortScheduleConflictView(APIView):
    """
    GET – check for schedule conflicts at the given day+time (teacher / admin only).
    Returns categorised conflict info without blocking.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, cohort_id):
        cohort = _get_cohort(self, slug, cohort_id)
        ensure_can_modify_course(request.user, cohort.course)

        try:
            day_of_week = int(request.query_params["day_of_week"])
            start_str   = request.query_params["start_time"]
            end_str     = request.query_params["end_time"]
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
            start_t = time_type(sh, sm)
            end_t   = time_type(eh, em)
        except (KeyError, ValueError, AttributeError):
            return Response(
                {"detail": "day_of_week, start_time, end_time are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule_id_param = request.query_params.get("schedule_id")
        exclude_id = int(schedule_id_param) if schedule_id_param and schedule_id_param.isdigit() else None

        conflicts = ScheduleService.get_schedule_conflicts(
            cohort.course.teacher_profile, day_of_week, start_t, end_t,
            exclude_cohort_schedule_id=exclude_id,
            cohort_start_date=cohort.start_date,
            cohort_duration_months=cohort.duration_months,
        )
        return Response(conflicts)
