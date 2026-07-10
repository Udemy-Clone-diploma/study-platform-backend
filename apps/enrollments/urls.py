from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.enrollments.views import (
    CourseCompletionView,
    CourseProgressView,
    EnrollmentGrowthView,
    EnrollmentViewSet,
    FreeEnrollmentView,
    LessonCompletionView,
    LessonOpenedView,
)

router = DefaultRouter()
router.register(r"enrollments", EnrollmentViewSet, basename="enrollments")

urlpatterns = [
    # Must precede the router include: the router's detail route
    # (`enrollments/<pk>/`) would otherwise swallow `enrollments/growth/`
    # by treating "growth" as a pk.
    path(
        "enrollments/growth/",
        EnrollmentGrowthView.as_view(),
        name="enrollment-growth",
    ),
    path("", include(router.urls)),
    path(
        "courses/<slug:slug>/enroll-free/",
        FreeEnrollmentView.as_view(),
        name="course-enroll-free",
    ),
    path(
        "courses/<slug:slug>/progress/",
        CourseProgressView.as_view(),
        name="course-progress",
    ),
    path(
        "courses/<slug:slug>/complete/",
        CourseCompletionView.as_view(),
        name="course-complete",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/complete/",
        LessonCompletionView.as_view(),
        name="lesson-complete",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/open/",
        LessonOpenedView.as_view(),
        name="lesson-open",
    ),
]
