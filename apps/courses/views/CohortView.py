from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Cohort
from apps.courses.serializers import CohortSerializer
from apps.courses.services import CohortService

from ._course_scoped import ensure_can_modify_course, get_course_for_request


@extend_schema(tags=["Cohorts"])
class CohortListCreateView(generics.ListCreateAPIView):
    serializer_class = CohortSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        return Cohort.objects.filter(course=course)

    def create(self, request, *args, **kwargs):
        course = get_course_for_request(self, self.kwargs["slug"])
        ensure_can_modify_course(request.user, course)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cohort = CohortService.create_for_course(course, serializer.validated_data)
        return Response(
            CohortSerializer(cohort, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Cohorts"])
class CohortDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CohortSerializer
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        return Cohort.objects.filter(course=course)

    def partial_update(self, request, *args, **kwargs):
        cohort = self.get_object()
        ensure_can_modify_course(request.user, cohort.course)
        serializer = self.get_serializer(cohort, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        cohort = CohortService.update_cohort(cohort, serializer.validated_data)
        return Response(CohortSerializer(cohort, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        cohort = self.get_object()
        ensure_can_modify_course(request.user, cohort.course)
        cohort.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
