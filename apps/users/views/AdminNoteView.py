from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.users.models import User
from apps.users.permissions import IsAdmin
from apps.users.serializers import AdminNoteSerializer
from apps.users.services.admin_note_service import AdminNoteService


@extend_schema(tags=["Users"])
class AdminNoteView(generics.GenericAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminNoteSerializer

    @extend_schema(responses=AdminNoteSerializer)
    def get(self, request, user_id: int):
        user = self._resolve_user(user_id)
        note = AdminNoteService.get_note(user)
        if note is None:
            return Response(
                {"detail": "Note not found."}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AdminNoteSerializer(note).data)

    @extend_schema(request=AdminNoteSerializer, responses=AdminNoteSerializer)
    def put(self, request, user_id: int):
        user = self._resolve_user(user_id)
        serializer = AdminNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = AdminNoteService.upsert_note(
            user, serializer.validated_data["content"], updated_by=request.user,
        )
        return Response(AdminNoteSerializer(note).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, user_id: int):
        user = self._resolve_user(user_id)
        AdminNoteService.delete_note(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _resolve_user(self, user_id: int) -> User:
        # all_objects: the admin list shows soft-deleted users, and notes on
        # them must stay reachable.
        user = User.all_objects.filter(pk=user_id).first()
        if user is None:
            raise NotFound("User not found.")
        if user == self.request.user:
            raise PermissionDenied("The note about a user is hidden from that user.")
        return user
