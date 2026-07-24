from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Exists, F, OuterRef
from rest_framework import filters, mixins, status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.courses.filters import CourseFilter
from apps.courses.models import Course, CourseDeliveryFormat
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
        "title",
        "min_price",
        "students_count",
        "students_enrolled_last_30_days",
        "rating_avg",
        "published_at",
        "created_at",
    ]
    ordering = ["-published_at"]

    def get_queryset(self):
        # DELETE archives via soft delete (status=archived + is_deleted=True),
        # so the admin table's Archived tab needs all_objects to see those rows.
        is_admin_list = self.action == "list" and self._is_admin_request()
        manager = Course.all_objects if is_admin_list else Course.objects
        queryset = (
            manager.select_related(
                "teacher_profile__user",
                "moderator_profile",
                "category",
            )
            .prefetch_related("tags")
        )
        queryset = CourseService.annotate_min_price(queryset)
        queryset = CourseService.annotate_recent_enrollments(queryset)
        if self.action == "list":
            if is_admin_list:
                # PENDING_EDIT rows are internal shadow drafts; the admin table
                # reads pending_edit_status off the live course row instead.
                queryset = queryset.exclude(
                    status=Course.StatusChoices.PENDING_EDIT
                )
            else:
                queryset = queryset.filter(status=Course.StatusChoices.PUBLISHED)
                # A course with no delivery format has no way to enroll or be
                # priced, so it shouldn't surface in the public catalog.
                queryset = queryset.filter(
                    Exists(CourseDeliveryFormat.objects.filter(course=OuterRef("pk")))
                )
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
                CourseService.delivery_formats_prefetch(),
                CourseService.cohorts_prefetch(),
            )
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        # DjangoFilterBackend's OrderingFilter does a plain order_by("-min_price"),
        # which on Postgres defaults to NULLS FIRST for descending order -- courses
        # with no pricing plan (min_price is NULL) would sort as if they were the
        # most expensive. Force NULLS LAST in both directions so unpriced courses
        # always sort to the end instead.
        ordering_param = self.request.query_params.get("ordering", "")
        if ordering_param in ("min_price", "-min_price"):
            descending = ordering_param.startswith("-")
            order_expr = F("min_price").desc(nulls_last=True) if descending else F("min_price").asc(nulls_last=True)
            queryset = queryset.order_by(order_expr)
        return queryset

    def _is_admin_request(self) -> bool:
        user = self.request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.RoleChoices.ADMINISTRATOR
        )

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
