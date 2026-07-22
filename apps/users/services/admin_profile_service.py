from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q

from apps.chat.models import ChatModerationAction
from apps.common.files import absolute_media_url
from apps.courses.models import (
    ApprovedCourseRecord,
    Category,
    Course,
    RejectedCourseRecord,
)
from apps.courses.serializers import ApprovedCourseRecordSerializer, RejectedCourseRecordSerializer
from apps.enrollments.models import Enrollment
from apps.schedule.models import Attendance
from apps.users.models import User, UserReport, UserReportAction
from apps.users.serializers import UserReportSerializer


class AdminProfileService:
    """Build the detailed profile data used by staff review screens."""

    @classmethod
    def build(cls, target: User, request) -> dict:
        result = {
            "user": cls._serialize_user(target, request),
        }

        if (
            target.role == User.RoleChoices.ADMINISTRATOR
            and request.user.role != User.RoleChoices.ADMINISTRATOR
        ):
            # Moderators and teachers may inspect an administrator from a
            # complaint, but only the personal profile is visible to them.
            result["details"] = {}
            return result

        report_stats = {
            "submitted": cls._report_stats(
                UserReport.objects.filter(reporter=target), request
            ),
            "received": cls._report_stats(
                UserReport.objects.filter(reported_user=target), request
            ),
        }
        result["report_stats"] = report_stats

        if target.role == User.RoleChoices.STUDENT:
            result["details"] = {"student": cls._student_details(target, request)}
        elif target.role == User.RoleChoices.TEACHER:
            result["details"] = {"teacher": cls._teacher_details(target, request)}
        elif target.role == User.RoleChoices.MODERATOR:
            result["details"] = {
                "moderator": cls._moderator_details(target, request),
            }
        else:
            result["details"] = {
                "administrator": cls._administrator_details(request),
            }

        return result

    @staticmethod
    def _serialize_user(user: User, request) -> dict:
        from apps.users.serializers import UserSerializer

        return UserSerializer(user, context={"request": request}).data

    @staticmethod
    def _user_summary(user: User | None, request) -> dict | None:
        if user is None:
            return None
        return {
            "id": user.id,
            "name": user.get_full_name() or user.email,
            "email": user.email,
            "role": user.role,
            "avatar": absolute_media_url(user.avatar, request),
        }

    @staticmethod
    def _course_summary(course: Course, request, *, enrollment: Enrollment | None = None) -> dict:
        teacher = course.teacher_profile.user
        payload = {
            "id": course.id,
            "title": course.title,
            "slug": course.slug,
            "image": absolute_media_url(course.image, request),
            "status": course.status,
            "category": course.category.name if course.category else None,
            "teacher": teacher.get_full_name() or teacher.email,
            "students_count": course.students_count,
            "created_at": course.created_at,
        }
        if enrollment is not None:
            payload["enrollment"] = {
                "id": enrollment.id,
                "order_id": enrollment.order_id,
                "access_status": enrollment.access_status,
                "access_granted_at": enrollment.access_granted_at,
                "access_until": enrollment.access_until,
                "progress_percent": round(
                    enrollment.lessons_completed_count * 100 / course.lessons_count
                )
                if course.lessons_count
                else 0,
                "attendance": AdminProfileService._attendance_summary(enrollment.id),
            }
        return payload

    @staticmethod
    def _attendance_summary(enrollment_id: int) -> dict:
        rows = list(
            Attendance.objects.filter(enrollment_id=enrollment_id)
            .values("session__date")
            .annotate(
                total=Count("id"),
                present=Count("id", filter=Q(is_present=True)),
            )
            .order_by("session__date")
        )
        total = sum(row["total"] for row in rows)
        present = sum(row["present"] for row in rows)
        grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in rows:
            date = row["session__date"]
            if date is None:
                continue
            key = date.strftime("%Y-%m")
            grouped[key][0] += row["present"]
            grouped[key][1] += row["total"]

        points = [
            {
                "label": key,
                "value": round(present_count * 100 / total_count) if total_count else 0,
                "present": present_count,
                "total": total_count,
            }
            for key, (present_count, total_count) in grouped.items()
        ]
        return {
            "present": present,
            "total": total,
            "percent": round(present * 100 / total) if total else 0,
            "points": points,
        }

    @classmethod
    def _student_details(cls, user: User, request) -> dict:
        enrollments = (
            Enrollment.objects.filter(student_profile__user=user)
            .select_related(
                "course",
                "course__category",
                "course__teacher_profile__user",
            )
            .order_by("-access_granted_at")
        )
        return {
            "courses": [
                cls._course_summary(enrollment.course, request, enrollment=enrollment)
                for enrollment in enrollments
            ],
        }

    @classmethod
    def _teacher_details(cls, user: User, request) -> dict:
        courses = list(
            Course.objects.filter(teacher_profile__user=user)
            .select_related("category", "teacher_profile__user")
            .order_by("-created_at")
        )
        total_students = (
            Enrollment.objects.filter(course_id__in=[course.id for course in courses])
            .values("student_profile_id")
            .distinct()
            .count()
        )
        return {
            "courses": [cls._course_summary(course, request) for course in courses],
            "total_students": total_students,
        }

    @classmethod
    def _moderator_details(cls, user: User, request) -> dict:
        return {
            "approved_courses": cls._course_records(
                ApprovedCourseRecord.objects.filter(moderator_profile__user=user),
                ApprovedCourseRecordSerializer,
                request,
            ),
            "rejected_courses": cls._course_records(
                RejectedCourseRecord.objects.filter(moderator_profile__user=user),
                RejectedCourseRecordSerializer,
                request,
            ),
            "message_reports": cls._message_report_actions(
                ChatModerationAction.objects.filter(moderator=user),
                request,
            ),
            "user_reports": cls._user_report_actions(
                UserReportAction.objects.filter(actor=user),
                request,
            ),
        }

    @classmethod
    def _administrator_details(cls, request) -> dict:
        return {
            "approved_courses": cls._course_records(
                ApprovedCourseRecord.objects.all(), ApprovedCourseRecordSerializer, request
            ),
            "rejected_courses": cls._course_records(
                RejectedCourseRecord.objects.all(), RejectedCourseRecordSerializer, request
            ),
            "message_reports": cls._message_report_actions(
                ChatModerationAction.objects.all(), request
            ),
            "user_reports": cls._user_report_actions(UserReportAction.objects.all(), request),
            "platform_stats": cls._platform_stats(),
        }

    @staticmethod
    def _course_records(queryset, serializer_class, request) -> list[dict]:
        records = queryset.order_by("-approved_at" if serializer_class is ApprovedCourseRecordSerializer else "-rejected_at")[:200]
        return serializer_class(records, many=True, context={"request": request}).data

    @classmethod
    def _message_report_actions(cls, queryset, request) -> list[dict]:
        actions = (
            queryset.exclude(report__isnull=True)
            .select_related(
                "target_user",
                "moderator",
                "report__message__sender",
                "report__message__chat",
                "report__reporter",
            )
            .order_by("-created_at", "-id")[:200]
        )
        return [
            {
                "id": action.id,
                "action": action.action,
                "action_label": action.get_action_display(),
                "processed_at": action.created_at,
                "note": action.note,
                "target_user": cls._user_summary(action.target_user, request),
                "processed_by": cls._user_summary(action.moderator, request),
                "report": {
                    "id": action.report.id,
                    "reason": action.report.reason,
                    "reason_label": action.report.get_reason_display(),
                    "message": action.report.message_text,
                    "message_created_at": action.report.message.created_at,
                    "reporter": cls._user_summary(action.report.reporter, request),
                },
            }
            for action in actions
        ]

    @classmethod
    def _user_report_actions(cls, queryset, request) -> list[dict]:
        actions = (
            queryset.exclude(action=UserReportAction.ActionChoices.CLAIMED)
            .select_related(
                "actor",
                "report__reported_user",
                "report__reporter",
            )
            .order_by("-created_at", "-id")[:200]
        )
        return [
            {
                "id": action.id,
                "action": action.action,
                "processed_at": action.created_at,
                "note": action.note,
                "processed_by": cls._user_summary(action.actor, request),
                "report": {
                    "id": action.report.id,
                    "reason": action.report.reason,
                    "reason_label": action.report.get_reason_display(),
                    "status": action.report.status,
                    "resolution": action.report.resolution,
                    "reported_user": cls._user_summary(action.report.reported_user, request),
                    "reporter": cls._user_summary(action.report.reporter, request),
                },
            }
            for action in actions
        ]

    @staticmethod
    def _report_stats(queryset, request) -> dict:
        status_counts = dict(queryset.values("status").annotate(count=Count("id")).values_list("status", "count"))
        reason_counts = dict(queryset.values("reason").annotate(count=Count("id")).values_list("reason", "count"))
        reports = (
            queryset.select_related(
                "reporter",
                "reported_user",
                "assigned_moderator__user",
                "escalated_by",
                "resolved_by",
            )
            .prefetch_related("actions__actor")
            .order_by("-created_at", "-id")
        )
        return {
            "total": queryset.count(),
            "by_status": [
                {"key": key, "label": label, "count": status_counts.get(key, 0)}
                for key, label in UserReport.StatusChoices.choices
            ],
            "by_reason": [
                {"key": key, "label": label, "count": reason_counts.get(key, 0)}
                for key, label in UserReport.ReasonChoices.choices
            ],
            "reports": UserReportSerializer(
                reports,
                many=True,
                context={"request": request},
            ).data,
        }

    @staticmethod
    def _platform_stats() -> dict:
        users = User.all_objects.all()
        courses = Course.all_objects.filter(is_deleted=False)
        categories = Category.all_objects.filter(is_deleted=False)
        return {
            "users": {
                "total": users.count(),
                "by_role": list(users.values("role").annotate(count=Count("id")).order_by("role")),
                "active": users.filter(is_deleted=False).count(),
            },
            "courses": {
                "total": courses.count(),
                "by_status": list(courses.values("status").annotate(count=Count("id")).order_by("status")),
            },
            "categories": {
                "total": categories.count(),
                "with_courses": categories.annotate(
                    course_count=Count("courses", filter=Q(courses__is_deleted=False))
                ).filter(course_count__gt=0).count(),
            },
        }
