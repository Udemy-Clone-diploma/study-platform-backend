from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses.views import CategoryViewSet, CourseViewSet

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")
router.register(r"categories", CategoryViewSet, basename="categories")

urlpatterns = [
    path("", include(router.urls)),
]
