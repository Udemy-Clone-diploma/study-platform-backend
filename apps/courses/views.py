from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from apps.courses.filters import CourseFilter
from apps.courses.models import Category, Course
from apps.courses.serializers import CategorySerializer
from apps.courses.services.course_service import CourseService


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class CourseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Course.objects.select_related(
        "teacher_profile__user",
        "moderator_profile",
        "category",
    ).prefetch_related("tags")
    http_method_names = ["get", "post", "patch", "delete"]
    filterset_class = CourseFilter

    def get_serializer_class(self):
        return CourseService.get_serializer_class(self.action)

    def create(self, request, *args, **kwargs):
        data = CourseService.create_course_from_data(
            request.data,
            context=self.get_serializer_context(),
        )
        return Response(
            data,
            status=status.HTTP_201_CREATED,
        )

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



class NewCoursesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        courses = CourseService.get_new_courses()
        return Response(courses)


class PopularCoursesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        courses = CourseService.get_popular_courses()
        return Response(courses)


class CategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = CourseService.get_categories()
        return Response(categories)