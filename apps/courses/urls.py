from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses.views import CourseViewSet

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")

urlpatterns = [
    path("", include(router.urls)),
]
