from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses.views import (
    CategoryViewSet,
    CourseViewSet,
    EnrolledCoursesView,
    FeaturedCategoriesView,
    NewCoursesView,
    PopularCoursesView,
    TeacherCoursesView,
)

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")
router.register(r"categories", CategoryViewSet, basename="categories")

urlpatterns = [
    path("courses/new-courses/", NewCoursesView.as_view(), name="new-courses"),
    path("courses/popular-courses/", PopularCoursesView.as_view(), name="popular-courses"),
    path("courses/my-courses/", TeacherCoursesView.as_view(), name="teacher-my-courses"),
    path("courses/enrolled/", EnrolledCoursesView.as_view(), name="enrolled-courses"),
    path(
        "categories/featured/",
        FeaturedCategoriesView.as_view(),
        name="categories-featured",
    ),
    path("", include(router.urls)),
]
