from django.urls import path

from apps.curriculum.views import (
    LessonDetailView,
    LessonSessionsView,
    MaterialsListView,
    NoteListView,
    NoteView,
    TestAttemptDetailView,
    TestAttemptView,
)

urlpatterns = [
    path(
        "notes/",
        NoteListView.as_view(),
        name="notes-list",
    ),
    path(
        "materials/",
        MaterialsListView.as_view(),
        name="materials-list",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/",
        LessonDetailView.as_view(),
        name="course-lesson-detail",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/sessions/",
        LessonSessionsView.as_view(),
        name="course-lesson-sessions",
    ),
    path(
        "courses/<slug:slug>/lessons/<int:lesson_id>/note/",
        NoteView.as_view(),
        name="course-lesson-note",
    ),
    path(
        "courses/<slug:slug>/tests/<int:test_id>/attempts/",
        TestAttemptView.as_view(),
        name="course-test-attempts",
    ),
    path(
        "courses/<slug:slug>/tests/<int:test_id>/attempts/<int:attempt_id>/",
        TestAttemptDetailView.as_view(),
        name="course-test-attempt-detail",
    ),
]
