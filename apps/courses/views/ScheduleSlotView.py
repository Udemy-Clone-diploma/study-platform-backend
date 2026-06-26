from datetime import datetime, timezone as dt_timezone

from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.exceptions import (
    InvalidScheduleTimeError,
    TeacherScheduleConflictError,
)
from django.db.models import Q

from apps.courses.models import CourseDeliveryFormat, EventInvitation, PersonalEvent, ScheduleSlot
from apps.courses.serializers import ScheduleSlotSerializer
from apps.courses.serializers.ScheduleSlotSerializer import (
    ScheduleSlotRescheduleSerializer,
    ScheduleSlotWriteSerializer,
)
from apps.courses.services import ScheduleService
from apps.enrollments.models import Enrollment
from apps.users.models import User

from ._course_scoped import ensure_can_modify_course, get_course_for_request


class _EnrollmentPeriodSerializer(serializers.Serializer):
    access_granted_at = serializers.DateField(required=False)
    access_until = serializers.DateField(required=False, allow_null=True)


def _get_delivery_format(view, slug: str, format_id: int) -> CourseDeliveryFormat:
    course = get_course_for_request(view, slug)
    try:
        return CourseDeliveryFormat.objects.get(
            pk=format_id,
            course=course,
            format_type=CourseDeliveryFormat.FormatType.INDIVIDUAL,
        )
    except CourseDeliveryFormat.DoesNotExist:
        raise NotFound("Individual delivery format not found.")


def _get_slot(view, slug: str, format_id: int, slot_id: int) -> ScheduleSlot:
    fmt = _get_delivery_format(view, slug, format_id)
    try:
        return ScheduleSlot.objects.get(pk=slot_id, delivery_format=fmt)
    except ScheduleSlot.DoesNotExist:
        raise NotFound("Schedule slot not found.")


@extend_schema(tags=["Schedule"])
class ScheduleSlotListCreateView(generics.GenericAPIView):
    """
    GET  – list slots.
      - Teacher / admin: all slots (booked + available).
      - Everyone else (including anonymous): only available (unbooked) slots.
    POST – teacher creates a new available slot.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, slug, format_id):
        fmt = _get_delivery_format(self, slug, format_id)
        user = request.user

        if (
            user.is_authenticated
            and user.role in (User.RoleChoices.TEACHER, User.RoleChoices.ADMINISTRATOR)
        ):
            slots = ScheduleService.get_all_slots(fmt)
        else:
            slots = ScheduleService.get_available_slots(fmt)

        serializer = ScheduleSlotSerializer(slots, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, slug, format_id):
        fmt = _get_delivery_format(self, slug, format_id)
        ensure_can_modify_course(request.user, fmt.course)

        serializer = ScheduleSlotWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            slot = ScheduleService.create_schedule_slot(fmt, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ScheduleSlotSerializer(slot, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Schedule"])
class ScheduleSlotDetailView(APIView):
    """
    GET    – retrieve a single slot.
    PATCH  – reschedule (teacher only).
    DELETE – delete slot (teacher only; cannot delete if booked).
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, slug, format_id, slot_id):
        slot = _get_slot(self, slug, format_id, slot_id)
        return Response(ScheduleSlotSerializer(slot, context={"request": request}).data)

    def patch(self, request, slug, format_id, slot_id):
        slot = _get_slot(self, slug, format_id, slot_id)
        ensure_can_modify_course(request.user, slot.delivery_format.course)

        serializer = ScheduleSlotRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            slot = ScheduleService.reschedule_slot(slot, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ScheduleSlotSerializer(slot, context={"request": request}).data)

    def delete(self, request, slug, format_id, slot_id):
        slot = _get_slot(self, slug, format_id, slot_id)
        ensure_can_modify_course(request.user, slot.delivery_format.course)

        if not slot.is_available:
            return Response(
                {"detail": "Cannot delete a slot that is already booked by a student."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Schedule"])
class ScheduleSlotAssignView(APIView):
    """POST – assign (or unassign) an enrolled student to a slot."""

    permission_classes = [IsAuthenticated]

    def post(self, request, slug, format_id, slot_id):
        slot = _get_slot(self, slug, format_id, slot_id)
        ensure_can_modify_course(request.user, slot.delivery_format.course)

        enrollment_id = request.data.get("enrollment_id")

        if enrollment_id is None:
            slot.booked_by = None
            slot.save(update_fields=["booked_by"])
            return Response(ScheduleSlotSerializer(slot, context={"request": request}).data)

        enrollment = get_object_or_404(
            Enrollment.objects.filter(course=slot.delivery_format.course),
            pk=enrollment_id,
        )

        slot.booked_by = enrollment
        slot.save(update_fields=["booked_by"])
        return Response(ScheduleSlotSerializer(slot, context={"request": request}).data)


@extend_schema(tags=["Schedule"])
class ScheduleSlotPersonalConflictView(APIView):
    """
    GET /courses/{slug}/delivery-formats/{formatId}/schedule-slots/{slotId}/personal-conflicts/
    Returns teacher's personal events (owned + invited) that overlap with the slot's
    recurring weekday+time.  Used before assigning a student to warn the teacher.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, slug, format_id, slot_id):
        slot = _get_slot(self, slug, format_id, slot_id)
        ensure_can_modify_course(request.user, slot.delivery_format.course)

        user     = request.user
        dow      = slot.day_of_week          # 0=Mon … 6=Sun
        iso_dow  = dow + 1                   # Django iso_week_day: 1=Mon … 7=Sun
        start_t  = slot.start_time
        end_t    = slot.end_time
        time_q   = Q(start_time__lt=end_t) & Q(end_time__gt=start_t)
        date_dow = Q(date__iso_week_day=iso_dow)

        # Personal events owned by the teacher on any matching weekday
        personal_qs = PersonalEvent.objects.filter(
            Q(owner=user) & date_dow & time_q
        ).order_by("date")

        # Accepted / pending invitations on matching weekday
        inv_qs = EventInvitation.objects.filter(
            invitee=user,
            status__in=[EventInvitation.Status.PENDING, EventInvitation.Status.ACCEPTED],
        ).filter(
            Q(event__date__iso_week_day=iso_dow)
            & Q(event__start_time__lt=end_t)
            & Q(event__end_time__gt=start_t)
        ).select_related("event").order_by("event__date")

        result = []
        for ev in personal_qs:
            result.append({
                "id":           ev.id,
                "title":        ev.title,
                "date":         ev.date.isoformat(),
                "start_time":   ev.start_time.strftime("%H:%M"),
                "end_time":     ev.end_time.strftime("%H:%M"),
                "is_owner":     True,
                "invitation_id": None,
            })
        for inv in inv_qs:
            result.append({
                "id":           inv.event_id,
                "title":        inv.event.title,
                "date":         inv.event.date.isoformat(),
                "start_time":   inv.event.start_time.strftime("%H:%M"),
                "end_time":     inv.event.end_time.strftime("%H:%M"),
                "is_owner":     False,
                "invitation_id": inv.id,
            })

        return Response(result)


@extend_schema(tags=["Schedule"])
class ScheduleSlotConflictView(APIView):
    """
    GET /courses/{slug}/delivery-formats/{formatId}/schedule-slots/reschedule-conflicts/
    Returns categorised conflicts for a proposed day+time without blocking.
    Query params: day_of_week, start_time, end_time, slot_id (self, to exclude)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, format_id):
        from datetime import time as time_type
        fmt = _get_delivery_format(self, slug, format_id)
        ensure_can_modify_course(request.user, fmt.course)

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
                status=400,
            )

        slot_id_param = request.query_params.get("slot_id")
        exclude_id = int(slot_id_param) if slot_id_param and slot_id_param.isdigit() else None

        conflicts = ScheduleService.get_schedule_conflicts(
            fmt.course.teacher_profile, day_of_week, start_t, end_t,
            exclude_slot_id=exclude_id,
        )
        return Response(conflicts)


@extend_schema(tags=["Schedule"])
class EnrollmentPeriodView(APIView):
    """PATCH – set start / end date for an individual-format enrollment (teacher only)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, format_id, enrollment_id):
        fmt = _get_delivery_format(self, slug, format_id)
        ensure_can_modify_course(request.user, fmt.course)

        enrollment = get_object_or_404(
            Enrollment.objects.filter(delivery_format=fmt),
            pk=enrollment_id,
        )

        serializer = _EnrollmentPeriodSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []
        if "access_granted_at" in data:
            d = data["access_granted_at"]
            enrollment.access_granted_at = datetime(d.year, d.month, d.day, tzinfo=dt_timezone.utc)
            update_fields.append("access_granted_at")
        if "access_until" in data:
            d = data["access_until"]
            enrollment.access_until = (
                datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=dt_timezone.utc)
                if d else None
            )
            update_fields.append("access_until")

        if update_fields:
            enrollment.save(update_fields=update_fields)

        from apps.courses.serializers.CohortGroupSerializer import EnrolledStudentSerializer
        return Response(EnrolledStudentSerializer(enrollment).data)
