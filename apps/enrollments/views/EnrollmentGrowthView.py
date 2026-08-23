from datetime import date, timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.models import User


def _bucket_enrollment_counts(qs, period: str) -> tuple[list[dict], int]:
    """New-enrollment count per week (last 6) or per month (current year)."""
    today = timezone.now().date()
    if period == "yearly":
        buckets = [date(today.year, m, 1) for m in range(1, 13)]
        labels = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        trunc = TruncMonth("access_granted_at")
    else:
        this_week = today - timedelta(days=today.weekday())
        buckets = [this_week - timedelta(weeks=5 - i) for i in range(6)]
        labels = [f"Week {i + 1}" for i in range(6)]
        trunc = TruncWeek("access_granted_at")

    windowed = qs.filter(access_granted_at__date__gte=buckets[0])
    grouped = {
        row["bucket"].date(): row["count"]
        for row in windowed.annotate(bucket=trunc).values("bucket").annotate(count=Count("id"))
    }
    points = [
        {
            "label": label,
            "date": bucket.isoformat(),
            "period": period,
            "value": grouped.get(bucket, 0),
        }
        for bucket, label in zip(buckets, labels, strict=True)
    ]
    return points, sum(p["value"] for p in points)


@extend_schema(tags=["Enrollments"])
class EnrollmentGrowthView(APIView):
    """GET /enrollments/growth/: new-enrollment count over time, for the teacher dashboard "Growth" widget."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period", "weekly")
        course_slug = request.query_params.get("course")
        user = request.user

        if user.role != User.RoleChoices.TEACHER:
            return Response({"total": 0, "points": [], "courses": []})

        # `courses` stays unfiltered regardless of `course_slug`, it feeds the
        # dropdown's full option list, not the chart data itself.
        courses = Course.objects.filter(teacher_profile=user.teacher_profile)
        enrollments = Enrollment.objects.filter(course__teacher_profile__user_id=user.id)
        if course_slug:
            enrollments = enrollments.filter(course__slug=course_slug)

        points, total = _bucket_enrollment_counts(enrollments, period)
        return Response(
            {
                "total": total,
                "points": points,
                "courses": [{"slug": c.slug, "title": c.title} for c in courses],
            }
        )
