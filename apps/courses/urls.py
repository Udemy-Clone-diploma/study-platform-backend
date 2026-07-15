from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses.views import (
    CategoryViewSet,
    CourseCertificatePreviewView,
    CourseApproveView,
    CourseAssignModeratorView,
    CourseRejectView,
    SaveReviewDraftView,
    CourseCopyToDraftView,
    CourseRestoreFromRejectedView,
    ModeratorApprovalRecordsView,
    ModeratorRejectionRecordsView,
    RejectedCoursesView,
    TeacherRejectionRecordsView,
    MyModerationCoursesView,
    MyRejectedModerationCoursesView,
    UnassignedModerationCoursesView,
    CohortDetailView,
    CohortMemberDetailView,
    CohortMemberListCreateView,
    CourseEnrolledStudentsView,
    TeacherStudentDashboardView,
    EnrollmentCompleteView,
    LessonDocumentDetailView,
    LessonDocumentListView,
    CohortListCreateView,
    CoursePendingEditApproveView,
    CoursePendingEditRejectView,
    CoursePendingEditSubmitView,
    CoursePendingEditView,
    CoursePendingEditWithdrawView,
    CourseViewSet,
    DeliveryFormatDetailView,
    DeliveryFormatListCreateView,
    EnrolledCoursesView,
    FeaturedCategoriesView,
    LessonItemViewSet,
    LessonViewSet,
    ModuleViewSet,
    NewCoursesView,
    PopularCoursesView,
    PricingPlanDetailView,
    PricingPlanListCreateView,
    QuestionViewSet,
    StudentCompletionsView,
    TeacherCoursesView,
    TestViewSet,
    WishlistListView,
    WishlistToggleView,
)

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")
router.register(r"categories", CategoryViewSet, basename="categories")

modules_router = DefaultRouter()
modules_router.register(r"modules", ModuleViewSet, basename="course-modules")

lessons_router = DefaultRouter()
lessons_router.register(r"lessons", LessonViewSet, basename="module-lessons")

lesson_items_router = DefaultRouter()
lesson_items_router.register(r"items", LessonItemViewSet, basename="lesson-items")

tests_router = DefaultRouter()
tests_router.register(r"tests", TestViewSet, basename="module-tests")

questions_router = DefaultRouter()
questions_router.register(r"questions", QuestionViewSet, basename="test-questions")

urlpatterns = [
    path("courses/new-courses/", NewCoursesView.as_view(), name="new-courses"),
    path("courses/popular-courses/", PopularCoursesView.as_view(), name="popular-courses"),
    path("courses/my-courses/", TeacherCoursesView.as_view(), name="teacher-my-courses"),
    path("courses/rejected/", RejectedCoursesView.as_view(), name="teacher-rejected-courses"),
    path("courses/<slug:slug>/restore-from-rejected/", CourseRestoreFromRejectedView.as_view(), name="course-restore-from-rejected"),
    path("courses/<slug:slug>/copy-to-draft/", CourseCopyToDraftView.as_view(), name="course-copy-to-draft"),
    path("courses/enrolled/", EnrolledCoursesView.as_view(), name="enrolled-courses"),
    path("courses/completions/", StudentCompletionsView.as_view(), name="student-completions"),
    path("courses/<slug:slug>/certificate-preview/", CourseCertificatePreviewView.as_view(), name="course-certificate-preview"),
    path("courses/moderation/unassigned/", UnassignedModerationCoursesView.as_view(), name="moderation-unassigned"),
    path("courses/moderation/my/", MyModerationCoursesView.as_view(), name="moderation-my"),
    path("courses/moderation/rejected/", MyRejectedModerationCoursesView.as_view(), name="moderation-rejected"),
    path("courses/moderation/rejection-records/", ModeratorRejectionRecordsView.as_view(), name="moderation-rejection-records"),
    path("courses/moderation/approval-records/", ModeratorApprovalRecordsView.as_view(), name="moderation-approval-records"),
    path("courses/my-rejection-records/", TeacherRejectionRecordsView.as_view(), name="teacher-rejection-records"),
    path("courses/<slug:slug>/assign-moderator/", CourseAssignModeratorView.as_view(), name="course-assign-moderator"),
    path("courses/wishlist/", WishlistListView.as_view(), name="wishlist-list"),
    path("courses/<slug:slug>/wishlist/", WishlistToggleView.as_view(), name="wishlist-toggle"),
    path("courses/<slug:slug>/approve/", CourseApproveView.as_view(), name="course-approve"),
    path("courses/<slug:slug>/reject/", CourseRejectView.as_view(), name="course-reject"),
    path("courses/<slug:slug>/save-review-draft/", SaveReviewDraftView.as_view(), name="save-review-draft"),
    path("courses/<slug:slug>/pending-edit/", CoursePendingEditView.as_view(), name="pending-edit"),
    path("courses/<slug:slug>/pending-edit/submit/", CoursePendingEditSubmitView.as_view(), name="pending-edit-submit"),
    path("courses/<slug:slug>/pending-edit/withdraw/", CoursePendingEditWithdrawView.as_view(), name="pending-edit-withdraw"),
    path("courses/<slug:slug>/pending-edit/approve/", CoursePendingEditApproveView.as_view(), name="pending-edit-approve"),
    path("courses/<slug:slug>/pending-edit/reject/", CoursePendingEditRejectView.as_view(), name="pending-edit-reject"),
    path(
        "courses/<slug:slug>/delivery-formats/",
        DeliveryFormatListCreateView.as_view(),
        name="delivery-formats-list",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:id>/",
        DeliveryFormatDetailView.as_view(),
        name="delivery-formats-detail",
    ),
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
        "courses/<slug:slug>/cohorts/<int:cohort_id>/members/",
        CohortMemberListCreateView.as_view(),
        name="cohort-members-list",
    ),
    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/members/<int:member_id>/",
        CohortMemberDetailView.as_view(),
        name="cohort-members-detail",
    ),
    path(
        "courses/<slug:slug>/enrolled-students/",
        CourseEnrolledStudentsView.as_view(),
        name="course-enrolled-students",
    ),
    path(
        "teacher/students/<int:student_id>/dashboard/",
        TeacherStudentDashboardView.as_view(),
        name="teacher-student-dashboard",
    ),
    path(
        "courses/<slug:slug>/students/<int:enrollment_id>/complete/",
        EnrollmentCompleteView.as_view(),
        name="enrollment-complete",
    ),
    path(
        "categories/featured/",
        FeaturedCategoriesView.as_view(),
        name="categories-featured",
    ),
    path("", include(router.urls)),
    path("courses/<slug:course_slug>/", include(modules_router.urls)),
    path("courses/<slug:course_slug>/modules/<int:module_pk>/", include(lessons_router.urls)),
    path(
        "courses/<slug:course_slug>/modules/<int:module_pk>/lessons/<int:lesson_pk>/",
        include(lesson_items_router.urls),
    ),
    path(
        "courses/<slug:course_slug>/modules/<int:module_pk>/lessons/<int:lesson_pk>/documents/",
        LessonDocumentListView.as_view(),
        name="lesson-documents",
    ),
    path(
        "courses/<slug:course_slug>/modules/<int:module_pk>/lessons/<int:lesson_pk>/documents/<int:doc_pk>/",
        LessonDocumentDetailView.as_view(),
        name="lesson-document-detail",
    ),
    path("courses/<slug:course_slug>/modules/<int:module_pk>/", include(tests_router.urls)),
    path(
        "courses/<slug:course_slug>/modules/<int:module_pk>/tests/<int:test_pk>/",
        include(questions_router.urls),
    ),
]
