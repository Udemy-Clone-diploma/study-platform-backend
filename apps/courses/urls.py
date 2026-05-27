from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses.views import (
    CategoryViewSet,
    CohortDetailView,
    CohortListCreateView,
    CourseViewSet,
    EnrolledCoursesView,
    FeaturedCategoriesView,
    NewCoursesView,
    PopularCoursesView,
    PricingPlanDetailView,
    PricingPlanListCreateView,
    TeacherCoursesView,
    WishlistListView,
    WishlistToggleView,
)

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")
router.register(r"categories", CategoryViewSet, basename="categories")

urlpatterns = [
    path("courses/new-courses/", NewCoursesView.as_view(), name="new-courses"),
    path("courses/popular-courses/", PopularCoursesView.as_view(), name="popular-courses"),
    path("courses/my-courses/", TeacherCoursesView.as_view(), name="teacher-my-courses"),
    path("courses/enrolled/", EnrolledCoursesView.as_view(), name="enrolled-courses"),
    path("courses/wishlist/", WishlistListView.as_view(), name="wishlist-list"),
    path("courses/<slug:slug>/wishlist/", WishlistToggleView.as_view(), name="wishlist-toggle"),
    path(
        "courses/<slug:slug>/pricing-plans/",
        PricingPlanListCreateView.as_view(),
        name="pricing-plans-list",
    ),
    path(
        "courses/<slug:slug>/pricing-plans/<int:id>/",
        PricingPlanDetailView.as_view(),
        name="pricing-plans-detail",
    ),
    path(
        "courses/<slug:slug>/cohorts/",
        CohortListCreateView.as_view(),
        name="cohorts-list",
    ),
    path(
        "courses/<slug:slug>/cohorts/<int:id>/",
        CohortDetailView.as_view(),
        name="cohorts-detail",
    ),
    path(
        "categories/featured/",
        FeaturedCategoriesView.as_view(),
        name="categories-featured",
    ),
    path("", include(router.urls)),
]
