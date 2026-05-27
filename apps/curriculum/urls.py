from django.urls import path

from apps.curriculum.views import LessonDetailView

urlpatterns = [
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/",
        LessonDetailView.as_view(),
        name="course-lesson-detail",
    ),
]
