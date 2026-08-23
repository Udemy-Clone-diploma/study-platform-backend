from django.urls import path

from apps.schedule.views import (
    CalendarEventUpdateView,
    CalendarView,
    CohortAttendanceView,
    CohortScheduleConflictView,
    CohortScheduleDetailView,
    CohortScheduleListCreateView,
    CohortSessionDatesView,
    EnrollmentPeriodView,
    EventInvitationStatusView,
    EventInviteView,
    EventParticipantsView,
    ExtraSessionView,
    IndividualAttendanceView,
    IndividualEnrollmentListView,
    IndividualSessionDatesView,
    InvitationListView,
    InvitationRespondView,
    PersonalEventConflictView,
    PersonalEventDetailView,
    PersonalEventView,
    ScheduleSlotAssignView,
    ScheduleSlotConflictView,
    ScheduleSlotDetailView,
    ScheduleSlotListCreateView,
    ScheduleSlotPersonalConflictView,
    TeacherUnavailabilityDetailView,
    TeacherUnavailabilityListCreateView,
)

urlpatterns = [
    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/schedules/",
        CohortScheduleListCreateView.as_view(),
        name="cohort-schedules-list",
    ),
    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/schedules/conflicts/",
        CohortScheduleConflictView.as_view(),
        name="cohort-schedule-conflicts",
    ),
    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/schedules/<int:schedule_id>/",
        CohortScheduleDetailView.as_view(),
        name="cohort-schedules-detail",
    ),

    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/schedule-slots/",
        ScheduleSlotListCreateView.as_view(),
        name="schedule-slots-list",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/schedule-slots/reschedule-conflicts/",
        ScheduleSlotConflictView.as_view(),
        name="schedule-slot-reschedule-conflicts",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/schedule-slots/<int:slot_id>/",
        ScheduleSlotDetailView.as_view(),
        name="schedule-slots-detail",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/schedule-slots/<int:slot_id>/assign/",
        ScheduleSlotAssignView.as_view(),
        name="schedule-slot-assign",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/schedule-slots/<int:slot_id>/personal-conflicts/",
        ScheduleSlotPersonalConflictView.as_view(),
        name="schedule-slot-personal-conflicts",
    ),
    path(
        "courses/<slug:slug>/delivery-formats/<int:format_id>/enrollments/<int:enrollment_id>/period/",
        EnrollmentPeriodView.as_view(),
        name="enrollment-period",
    ),

    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/session-dates/",
        CohortSessionDatesView.as_view(),
        name="cohort-session-dates",
    ),
    path(
        "courses/<slug:slug>/cohorts/<int:cohort_id>/attendance/",
        CohortAttendanceView.as_view(),
        name="cohort-attendance",
    ),

    path(
        "courses/<slug:slug>/individual-enrollments/",
        IndividualEnrollmentListView.as_view(),
        name="individual-enrollments",
    ),
    path(
        "courses/<slug:slug>/enrollments/<int:enrollment_id>/session-dates/",
        IndividualSessionDatesView.as_view(),
        name="enrollment-session-dates",
    ),
    path(
        "courses/<slug:slug>/enrollments/<int:enrollment_id>/attendance/",
        IndividualAttendanceView.as_view(),
        name="enrollment-attendance",
    ),

    path(
        "teacher/unavailability/",
        TeacherUnavailabilityListCreateView.as_view(),
        name="teacher-unavailability-list",
    ),
    path(
        "teacher/unavailability/<int:block_id>/",
        TeacherUnavailabilityDetailView.as_view(),
        name="teacher-unavailability-detail",
    ),

    path("calendar/", CalendarView.as_view(), name="calendar"),
    path("calendar/events/extra/",                           ExtraSessionView.as_view(),            name="extra-session-create"),
    path("calendar/events/personal/conflicts/",              PersonalEventConflictView.as_view(),   name="personal-event-conflicts"),
    path("calendar/events/personal/",                        PersonalEventView.as_view(),           name="personal-event-create"),
    path("calendar/events/personal/<int:pk>/invite/",        EventInviteView.as_view(),             name="personal-event-invite"),
    path("calendar/events/personal/<int:pk>/invitations/",   EventInvitationStatusView.as_view(),   name="personal-event-invitations"),
    path("calendar/events/personal/<int:pk>/participants/",  EventParticipantsView.as_view(),       name="personal-event-participants"),
    path("calendar/events/personal/<int:pk>/",               PersonalEventDetailView.as_view(),     name="personal-event-detail"),
    path("calendar/events/<str:event_id>/",                  CalendarEventUpdateView.as_view(),     name="calendar-event-update"),
    path("calendar/invitations/",                            InvitationListView.as_view(),          name="invitation-list"),
    path("calendar/invitations/<int:pk>/",                   InvitationRespondView.as_view(),       name="invitation-respond"),
]