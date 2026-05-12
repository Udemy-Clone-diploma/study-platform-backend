from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsSetPagination
from apps.courses.serializers import CourseListSerializer
from apps.courses.services import CourseService
from apps.users.permissions import IsTeacher


@extend_schema(tags=["Courses"])
class TeacherCoursesView(APIView):
    permission_classes = [IsTeacher]

    @extend_schema(
        summary="List the current teacher's own courses",
        description="Returns all non-deleted courses created by the authenticated teacher, across all statuses.",
        responses={200: CourseListSerializer(many=True)},
    )
    def get(self, request):
        courses = CourseService.get_teacher_courses_queryset(request.user.teacher_profile)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(courses, request)
        serializer = CourseListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
