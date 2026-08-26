from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.exceptions import DuplicateDeliveryFormatError
from apps.courses.models import CourseDeliveryFormat
from apps.courses.serializers import (
    CourseDeliveryFormatSerializer,
    CourseDeliveryFormatWriteSerializer,
)
from apps.courses.services import DeliveryFormatService

from ._course_scoped import (
    ensure_can_modify_course,
    ensure_can_view_course_management,
    get_course_for_request,
)


@extend_schema(tags=["DeliveryFormats"])
class DeliveryFormatListCreateView(generics.ListCreateAPIView):
    def get_permissions(self):
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return (
            CourseDeliveryFormatWriteSerializer
            if self.request.method == "POST"
            else CourseDeliveryFormatSerializer
        )

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_view_course_management(self.request.user, course)
        return CourseDeliveryFormat.objects.filter(course=course).select_related("pricing")

    def create(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        serializer = CourseDeliveryFormatWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            fmt = DeliveryFormatService.create_for_course(course, serializer.validated_data)
        except DuplicateDeliveryFormatError as exc:
            return Response({"format_type": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CourseDeliveryFormatSerializer(fmt).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["DeliveryFormats"])
class DeliveryFormatDetailView(generics.RetrieveUpdateDestroyAPIView):
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return (
            CourseDeliveryFormatWriteSerializer
            if self.request.method == "PATCH"
            else CourseDeliveryFormatSerializer
        )

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_view_course_management(self.request.user, course)
        return CourseDeliveryFormat.objects.filter(course=course).select_related("pricing")

    def partial_update(self, request, *args, **kwargs):
        fmt = self.get_object()
        ensure_can_modify_course(request.user, fmt.course)
        serializer = CourseDeliveryFormatWriteSerializer(fmt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            fmt = DeliveryFormatService.update_format(fmt, serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CourseDeliveryFormatSerializer(fmt).data)

    def destroy(self, request, *args, **kwargs):
        fmt = self.get_object()
        ensure_can_modify_course(request.user, fmt.course)
        fmt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
