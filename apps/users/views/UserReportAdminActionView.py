from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.common.serializers import MessageSerializer
from apps.users.exceptions import (
    LastAdministratorError,
    UserReportConflictError,
    UserReportNotFoundError,
    UserReportPermissionError,
)
from apps.users.permissions import IsAdmin
from apps.users.serializers import (
    AdminUserReportActionSerializer,
    UserReportSerializer,
)
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportAdminActionView(GenericAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminUserReportActionSerializer

    @extend_schema(
        responses={
            200: UserReportSerializer,
            400: MessageSerializer,
            403: MessageSerializer,
            404: MessageSerializer,
            409: MessageSerializer,
        }
    )
    def post(self, request, report_id: int):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = UserReportService.admin_action(
                report_id,
                request.user,
                **serializer.validated_data,
            )
        except UserReportNotFoundError:
            return Response(
                {"detail": "Report not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except UserReportPermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except (UserReportConflictError, LastAdministratorError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(UserReportSerializer(report, context={"request": request}).data)
