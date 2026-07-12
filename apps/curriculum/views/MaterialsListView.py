from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.curriculum.models import Lesson
from apps.curriculum.serializers import MaterialsLessonSerializer
from apps.enrollments.models import Enrollment
from apps.users.models import User


@extend_schema(tags=["Materials"])
class MaterialsListView(ListAPIView):
    """GET /materials/ — every lesson with attached documents across the student's
    enrolled courses (the "Educational materials" library). No pagination -- the
    page itself renders the full, month-grouped list at once."""

    permission_classes = [IsAuthenticated]
    serializer_class = MaterialsLessonSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if user.role != User.RoleChoices.STUDENT:
            return Lesson.objects.none()

        course_ids = Enrollment.objects.with_active_access().filter(
            student_profile=user.student_profile,
        ).values_list("course_id", flat=True)

        qs = (
            Lesson.objects.filter(module__course_id__in=course_ids, documents__isnull=False)
            .select_related("module__course")
            .prefetch_related("documents")
            .distinct()
            .order_by("-created_at")
        )

        course_slug = self.request.query_params.get("course")
        if course_slug:
            qs = qs.filter(module__course__slug=course_slug)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(module__course__title__icontains=search))

        return qs
