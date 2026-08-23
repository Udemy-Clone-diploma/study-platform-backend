from django.urls import path

from apps.homework.views import (
    HomeworkAssignmentAttachmentDetailView,
    HomeworkAssignmentAttachmentView,
    HomeworkAssignmentCloseView,
    HomeworkAssignmentDetailView,
    HomeworkAssignmentListCreateView,
    HomeworkAssignmentPublishView,
    HomeworkAvailableRecipientsView,
    HomeworkGrowthView,
    HomeworkSubmissionRetrieveView,
    HomeworkSubmissionReviewView,
    StudentHomeworkListView,
    StudentHomeworkSubmissionAttachmentDetailView,
    StudentHomeworkSubmissionAttachmentView,
    StudentHomeworkSubmissionView,
)

urlpatterns = [
    path(
        "courses/<slug:slug>/homework/",
        HomeworkAssignmentListCreateView.as_view(),
        name="homework-assignment-list",
    ),
    path("courses/<slug:slug>/homework/recipients/", HomeworkAvailableRecipientsView.as_view(), name="homework-available-recipients"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/", HomeworkAssignmentDetailView.as_view(), name="homework-assignment-detail"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/publish/", HomeworkAssignmentPublishView.as_view(), name="homework-assignment-publish"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/close/", HomeworkAssignmentCloseView.as_view(), name="homework-assignment-close"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/attachments/", HomeworkAssignmentAttachmentView.as_view(), name="homework-assignment-attachment-list"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/attachments/<int:attachment_id>/", HomeworkAssignmentAttachmentDetailView.as_view(), name="homework-assignment-attachment-detail"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/submissions/<int:submission_id>/", HomeworkSubmissionReviewView.as_view(), name="homework-submission-review"),
    path("courses/<slug:slug>/homework/<int:assignment_id>/submissions/<int:submission_id>/retrieve/", HomeworkSubmissionRetrieveView.as_view(), name="homework-submission-retrieve"),
    path("homework/growth/", HomeworkGrowthView.as_view(), name="homework-growth"),
    path("homework/assigned/", StudentHomeworkListView.as_view(), name="student-homework-list"),
    path("homework/<int:assignment_id>/submission/", StudentHomeworkSubmissionView.as_view(), name="student-homework-submission"),
    path("homework/<int:assignment_id>/submission/attachments/", StudentHomeworkSubmissionAttachmentView.as_view(), name="student-homework-submission-attachment-list"),
    path("homework/<int:assignment_id>/submission/attachments/<int:attachment_id>/", StudentHomeworkSubmissionAttachmentDetailView.as_view(), name="student-homework-submission-attachment-detail"),
]
