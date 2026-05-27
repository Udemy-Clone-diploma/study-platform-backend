from django.urls import path

from apps.reviews.views import CourseReviewsView

urlpatterns = [
    path(
        "courses/<slug:slug>/reviews/",
        CourseReviewsView.as_view(),
        name="course-reviews",
    ),
]
