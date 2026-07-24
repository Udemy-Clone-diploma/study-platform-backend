from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TypedDict

from django.utils import timezone

from apps.chat.models import ChatModerationAction, MessageReport
from apps.courses.models import (
    ApprovedCourseRecord,
    Course,
    CoursePendingEdit,
    RejectedCourseRecord,
)
from apps.reviews.constants import REVIEW_MODERATION_REPORT_THRESHOLD
from apps.reviews.models import Review
from apps.users.models import ModeratorProfile, User, UserReport, UserReportAction


class ModerationEvent(TypedDict):
    occurred_at: datetime
    source: str
    outcome: str
    duration_seconds: float | None
    restrictive: bool
    reversal: bool


class ModeratorStatisticsService:
    """Build real moderator workload and performance statistics from audit data."""

    PERIOD_DAYS = 7
    SOURCE_LABELS = {
        "user_reports": "User reports",
        "chat_reports": "Chat safety",
        "course_reviews": "Course review",
        "reported_reviews": "Content quality",
    }

    @classmethod
    def build(cls, moderator: User) -> dict:
        profile = getattr(moderator, "moderator_profile", None)
        if profile is None:
            raise ModeratorProfile.DoesNotExist

        now = timezone.now()
        today = timezone.localdate(now)
        current_start_date = today - timedelta(days=cls.PERIOD_DAYS - 1)
        current_start = timezone.make_aware(
            datetime.combine(current_start_date, time.min),
            timezone.get_current_timezone(),
        )
        previous_start = current_start - timedelta(days=cls.PERIOD_DAYS)

        events = cls._collect_events(
            moderator=moderator,
            profile=profile,
            since=previous_start,
        )
        current_events = [
            event for event in events if current_start <= event["occurred_at"] <= now
        ]
        previous_events = [
            event
            for event in events
            if previous_start <= event["occurred_at"] < current_start
        ]

        current_blocked = cls._outcome_count(current_events, "blocked")
        previous_blocked = cls._outcome_count(previous_events, "blocked")
        current_reversal_rate = cls._reversal_rate(current_events)
        previous_reversal_rate = cls._reversal_rate(previous_events)
        current_average_hours = cls._average_review_hours(current_events)
        previous_average_hours = cls._average_review_hours(previous_events)

        return {
            "period": {
                "days": cls.PERIOD_DAYS,
                "start": current_start_date.isoformat(),
                "end": today.isoformat(),
            },
            "metrics": {
                "total_reviewed": cls._metric(
                    len(current_events),
                    cls._percent_change(len(current_events), len(previous_events)),
                    "count",
                ),
                "harmful_content_blocked": cls._metric(
                    current_blocked,
                    cls._percent_change(current_blocked, previous_blocked),
                    "count",
                ),
                "pending_reviews": cls._metric(
                    cls._pending_count(profile),
                    None,
                    "count",
                ),
                "reversal_rate": cls._metric(
                    current_reversal_rate,
                    round(current_reversal_rate - previous_reversal_rate, 1),
                    "percent",
                    change_kind="percentage_points",
                ),
                "average_review_time": cls._metric(
                    current_average_hours,
                    cls._percent_change(current_average_hours, previous_average_hours),
                    "hours",
                ),
            },
            "trends": cls._trend_rows(current_events, current_start_date),
            "categories": cls._category_rows(current_events),
        }

    @classmethod
    def _collect_events(
        cls,
        *,
        moderator: User,
        profile: ModeratorProfile,
        since: datetime,
    ) -> list[ModerationEvent]:
        events: list[ModerationEvent] = []

        user_actions = (
            UserReportAction.objects.filter(actor=moderator, created_at__gte=since)
            .exclude(action=UserReportAction.ActionChoices.CLAIMED)
            .select_related("report")
        )
        for action in user_actions:
            outcome = cls._user_report_outcome(action.action)
            events.append(
                cls._event(
                    occurred_at=action.created_at,
                    source="user_reports",
                    outcome=outcome,
                    started_at=action.report.created_at,
                    restrictive=action.action
                    in {
                        UserReportAction.ActionChoices.WARNING,
                        UserReportAction.ActionChoices.BLOCKED,
                    },
                    reversal=action.action == UserReportAction.ActionChoices.UNBLOCKED,
                )
            )

        chat_actions = ChatModerationAction.objects.filter(
            moderator=moderator,
            created_at__gte=since,
        ).select_related("report")
        for action in chat_actions:
            outcome = cls._chat_outcome(action.action)
            events.append(
                cls._event(
                    occurred_at=action.created_at,
                    source="chat_reports",
                    outcome=outcome,
                    started_at=action.report.created_at if action.report else None,
                    restrictive=action.action
                    in {
                        ChatModerationAction.ActionChoices.WARNING,
                        ChatModerationAction.ActionChoices.RESTRICT,
                    },
                    reversal=action.action
                    in {
                        ChatModerationAction.ActionChoices.RETRACT_WARNING,
                        ChatModerationAction.ActionChoices.RESTORE,
                    },
                )
            )

        approvals = ApprovedCourseRecord.objects.filter(
            moderator_profile=profile,
            approved_at__gte=since,
        ).select_related("course")
        for record in approvals:
            events.append(
                cls._event(
                    occurred_at=record.approved_at,
                    source="course_reviews",
                    outcome="approved",
                    started_at=(
                        record.course.created_at
                        if record.course_id and not record.changed_fields
                        else None
                    ),
                )
            )

        rejections = RejectedCourseRecord.objects.filter(
            moderator_profile=profile,
            rejected_at__gte=since,
        ).select_related("course")
        for record in rejections:
            events.append(
                cls._event(
                    occurred_at=record.rejected_at,
                    source="course_reviews",
                    outcome="blocked",
                    started_at=(
                        record.course.created_at
                        if record.course_id and not record.changed_fields
                        else None
                    ),
                    restrictive=True,
                )
            )

        moderated_reviews = (
            Review.all_objects.filter(
                moderator_profile=profile,
                moderated_at__gte=since,
                moderation_status__in=[
                    Review.ModerationStatusChoices.APPROVED,
                    Review.ModerationStatusChoices.REJECTED,
                ],
            )
            .prefetch_related("reports")
            .order_by()
        )
        for review in moderated_reviews:
            reports = sorted(review.reports.all(), key=lambda item: item.created_at)
            threshold_index = REVIEW_MODERATION_REPORT_THRESHOLD - 1
            started_at = (
                reports[threshold_index].created_at
                if len(reports) > threshold_index
                else review.created_at
            )
            rejected = review.moderation_status == Review.ModerationStatusChoices.REJECTED
            events.append(
                cls._event(
                    occurred_at=review.moderated_at,
                    source="reported_reviews",
                    outcome="blocked" if rejected else "approved",
                    started_at=started_at,
                    restrictive=rejected,
                )
            )

        return events

    @staticmethod
    def _event(
        *,
        occurred_at: datetime,
        source: str,
        outcome: str,
        started_at: datetime | None = None,
        restrictive: bool = False,
        reversal: bool = False,
    ) -> ModerationEvent:
        duration_seconds = None
        if started_at is not None:
            duration_seconds = max(0.0, (occurred_at - started_at).total_seconds())
        return {
            "occurred_at": occurred_at,
            "source": source,
            "outcome": outcome,
            "duration_seconds": duration_seconds,
            "restrictive": restrictive,
            "reversal": reversal,
        }

    @staticmethod
    def _user_report_outcome(action: str) -> str:
        if action == UserReportAction.ActionChoices.BLOCKED:
            return "blocked"
        if action in {
            UserReportAction.ActionChoices.WARNING,
            UserReportAction.ActionChoices.ESCALATED,
        }:
            return "flagged"
        return "approved"

    @staticmethod
    def _chat_outcome(action: str) -> str:
        if action == ChatModerationAction.ActionChoices.RESTRICT:
            return "blocked"
        if action == ChatModerationAction.ActionChoices.WARNING:
            return "flagged"
        return "approved"

    @staticmethod
    def _pending_count(profile: ModeratorProfile) -> int:
        user_reports = UserReport.objects.filter(
            assigned_moderator=profile,
            status=UserReport.StatusChoices.IN_REVIEW,
        ).count()
        chat_reports = MessageReport.objects.filter(
            moderation_actions__isnull=True,
        ).count()
        courses = Course.objects.filter(
            moderator_profile=profile,
            status=Course.StatusChoices.REVIEW,
        ).count()
        course_edits = CoursePendingEdit.objects.filter(
            moderator_profile=profile,
            status=CoursePendingEdit.StatusChoices.PENDING,
        ).count()
        reviews = Review.all_objects.filter(
            moderator_profile=profile,
            moderation_status=Review.ModerationStatusChoices.PENDING,
        ).count()
        return user_reports + chat_reports + courses + course_edits + reviews

    @classmethod
    def _trend_rows(
        cls,
        events: list[ModerationEvent],
        start_date,
    ) -> list[dict]:
        rows = []
        for offset in range(cls.PERIOD_DAYS):
            day = start_date + timedelta(days=offset)
            day_events = [
                event
                for event in events
                if timezone.localtime(event["occurred_at"]).date() == day
            ]
            rows.append(
                {
                    "date": day.isoformat(),
                    "label": f"{day.strftime('%b')} {day.day}",
                    "reviewed": len(day_events),
                    "blocked": cls._outcome_count(day_events, "blocked"),
                    "flagged": cls._outcome_count(day_events, "flagged"),
                    "approved": cls._outcome_count(day_events, "approved"),
                }
            )
        return rows

    @classmethod
    def _category_rows(cls, events: list[ModerationEvent]) -> list[dict]:
        total = len(events)
        return [
            {
                "key": key,
                "label": label,
                "count": sum(event["source"] == key for event in events),
                "percent": (
                    round(
                        100
                        * sum(event["source"] == key for event in events)
                        / total
                    )
                    if total
                    else 0
                ),
            }
            for key, label in cls.SOURCE_LABELS.items()
        ]

    @staticmethod
    def _outcome_count(events: list[ModerationEvent], outcome: str) -> int:
        return sum(event["outcome"] == outcome for event in events)

    @staticmethod
    def _reversal_rate(events: list[ModerationEvent]) -> float:
        decisions = sum(
            event["restrictive"] or event["reversal"] for event in events
        )
        reversals = sum(event["reversal"] for event in events)
        return round(100 * reversals / decisions, 1) if decisions else 0.0

    @staticmethod
    def _average_review_hours(events: list[ModerationEvent]) -> float | None:
        durations = [
            event["duration_seconds"]
            for event in events
            if event["duration_seconds"] is not None
        ]
        if not durations:
            return None
        return round(sum(durations) / len(durations) / 3600, 1)

    @staticmethod
    def _percent_change(current, previous) -> float | None:
        if current is None or previous is None:
            return None
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round((current - previous) / previous * 100, 1)

    @staticmethod
    def _metric(
        value,
        change,
        unit: str,
        *,
        change_kind: str = "percent",
    ) -> dict:
        return {
            "value": value,
            "unit": unit,
            "change": change,
            "change_kind": change_kind if change is not None else None,
        }
