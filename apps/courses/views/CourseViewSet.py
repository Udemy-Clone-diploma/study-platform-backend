from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.courses.filters import CourseFilter
from apps.courses.models import Course
from apps.courses.permissions import IsCourseOwnerOrAdmin
from apps.courses.serializers import (
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
)
from apps.courses.services.course_service import CourseService
from apps.users.models import User
from apps.users.permissions import IsTeacherOrAdmin


@extend_schema(tags=["Courses"])
class CourseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "slug"
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CourseFilter
    ordering_fields = [
        "min_price",
        "students_count",
        "students_enrolled_last_30_days",
        "rating_avg",
        "published_at",
        "created_at",
    ]
    ordering = ["-published_at"]

    def get_queryset(self):
        queryset = (
            Course.objects.select_related(
                "teacher_profile__user",
                "moderator_profile",
                "category",
            )
            .prefetch_related("tags")
        )
        queryset = CourseService.annotate_min_price(queryset)
        queryset = CourseService.annotate_recent_enrollments(queryset)
        if self.action == "list":
            queryset = queryset.filter(status=Course.StatusChoices.PUBLISHED)
        elif self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "modules",
                "modules__lessons",
                "modules__lessons__documents",
                "modules__lessons__items",
                "modules__lessons__items__test",
                "modules__lessons__items__test__questions",
                "modules__tests",
                "modules__tests__questions",
                "delivery_formats",
                "delivery_formats__pricing",
                "cohorts",
            )
        return queryset

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action == "create":
            return [IsTeacherOrAdmin()]
        if self.action in {"partial_update", "destroy"}:
            return [IsCourseOwnerOrAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "list":
            return CourseListSerializer
        if self.action in {"create", "partial_update"}:
            return CourseCreateUpdateSerializer
        return CourseDetailSerializer

    def get_object(self):
        obj = super().get_object()
        if self.action == "retrieve" and not self._can_view_course(obj):
            raise NotFound()
        return obj

    def _can_view_course(self, course: Course) -> bool:
        if course.status == Course.StatusChoices.PUBLISHED:
            return True
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.role in (
            User.RoleChoices.ADMINISTRATOR,
            User.RoleChoices.MODERATOR,
        ):
            return True
        if course.teacher_profile.user_id == user.id:
            return True
        if course.status == Course.StatusChoices.HIDDEN:
            from apps.enrollments.models import Enrollment
            try:
                return Enrollment.objects.with_active_access().filter(
                    student_profile=user.student_profile,
                    course=course,
                ).exists()
            except Exception:
                return False
        return False

    def create(self, request, *args, **kwargs):
        data = CourseService.create_course_from_data(
            request.data,
            context=self.get_serializer_context(),
        )
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        course = self.get_object()
        data = CourseService.update_course_from_data(
            course,
            request.data,
            context=self.get_serializer_context(),
        )
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        CourseService.soft_delete_course(course)
        return Response(status=status.HTTP_204_NO_CONTENT)
