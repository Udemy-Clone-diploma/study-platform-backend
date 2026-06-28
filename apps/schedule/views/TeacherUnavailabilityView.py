from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schedule.exceptions import InvalidScheduleTimeError, TeacherScheduleConflictError
from apps.schedule.models import TeacherUnavailability
from apps.schedule.serializers import TeacherUnavailabilitySerializer, TeacherUnavailabilityWriteSerializer
from apps.schedule.services import ScheduleService
from apps.users.models import TeacherProfile, User


def _get_teacher_profile(user) -> TeacherProfile:
    if user.role not in (User.RoleChoices.TEACHER, User.RoleChoices.ADMINISTRATOR):
        raise PermissionDenied("Only teachers can manage unavailability blocks.")
    try:
        return user.teacher_profile
    except TeacherProfile.DoesNotExist:
        raise PermissionDenied("Teacher profile not found.")


@extend_schema(tags=["Schedule"])
class TeacherUnavailabilityListCreateView(APIView):
    """
    GET  – list the authenticated teacher's unavailability blocks.
    POST – add a new block (teacher / admin only).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        teacher = _get_teacher_profile(request.user)
        blocks  = TeacherUnavailability.objects.filter(teacher_profile=teacher)
        return Response(TeacherUnavailabilitySerializer(blocks, many=True).data)

    def post(self, request):
        teacher = _get_teacher_profile(request.user)

        serializer = TeacherUnavailabilityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            block = ScheduleService.create_unavailability(teacher, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            TeacherUnavailabilitySerializer(block).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Schedule"])
class TeacherUnavailabilityDetailView(APIView):
    """
    GET    – retrieve a single block.
    PATCH  – update.
    DELETE – remove.
    """
    permission_classes = [IsAuthenticated]

    def _get_block(self, user, block_id: int) -> TeacherUnavailability:
        teacher = _get_teacher_profile(user)
        try:
            return TeacherUnavailability.objects.get(pk=block_id, teacher_profile=teacher)
        except TeacherUnavailability.DoesNotExist:
            raise NotFound("Unavailability block not found.")

    def get(self, request, block_id):
        block = self._get_block(request.user, block_id)
        return Response(TeacherUnavailabilitySerializer(block).data)

    def patch(self, request, block_id):
        block = self._get_block(request.user, block_id)

        serializer = TeacherUnavailabilityWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            block = ScheduleService.update_unavailability(block, serializer.validated_data)
        except (TeacherScheduleConflictError, InvalidScheduleTimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TeacherUnavailabilitySerializer(block).data)

    def delete(self, request, block_id):
        block = self._get_block(request.user, block_id)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)