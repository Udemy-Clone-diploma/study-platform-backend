from django.urls import path

from apps.homework.views import HomeworkAssignmentListCreateView


urlpatterns = [
    path(
        "courses/<slug:slug>/homework/",
        HomeworkAssignmentListCreateView.as_view(),
        name="homework-assignment-list",
    ),
]
