from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.serializers import MessageSerializer
from apps.users.exceptions import (
    UserReportConflictError,
    UserReportNotFoundError,
    UserReportPermissionError,
)
from apps.users.permissions import IsModerator
from apps.users.serializers import UserReportSerializer
from apps.users.services import UserReportService


@extend_schema(tags=["User moderation"])
class UserReportClaimView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(
        request=None,
        responses={
            200: UserReportSerializer,
            403: MessageSerializer,
            404: MessageSerializer,
            409: MessageSerializer,
        },
    )
    def post(self, request, report_id: int):
        try:
            report = UserReportService.claim_report(report_id, request.user)
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
        except UserReportConflictError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(UserReportSerializer(report, context={"request": request}).data)
