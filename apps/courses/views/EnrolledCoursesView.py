from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsSetPagination
from apps.courses.serializers import CourseListSerializer
from apps.courses.services import CourseService
from apps.users.permissions import IsStudent


@extend_schema(tags=["Courses"])
class EnrolledCoursesView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        summary="List courses the current student is enrolled in",
        description="Returns all non-deleted courses the authenticated student has enrolled in.",
        responses={200: CourseListSerializer(many=True)},
    )
    def get(self, request):
        courses = CourseService.get_enrolled_courses_queryset(request.user.student_profile)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(courses, request)
        serializer = CourseListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
