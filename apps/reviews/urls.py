from django.urls import path

from apps.reviews.views import CourseReviewsView, TopReviewsView

urlpatterns = [
    path(
        "courses/<slug:slug>/reviews/",
        CourseReviewsView.as_view(),
        name="course-reviews",
    ),
    path(
        "reviews/top-reviews/",
        TopReviewsView.as_view(),
        name="top-reviews",
    ),
]
