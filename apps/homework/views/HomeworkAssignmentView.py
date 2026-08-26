from datetime import date, timedelta

from django.db import transaction
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth, TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Cohort, Course, CourseDeliveryFormat
from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.models import TestAttempt
from apps.enrollments.models import Enrollment
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentAttachment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
    HomeworkSubmissionAttachment,
)
from apps.homework.serializers import (
    HomeworkAssignmentAttachmentSerializer,
    HomeworkAssignmentSerializer,
    HomeworkAvailableRecipientSerializer,
    HomeworkFileUploadSerializer,
    HomeworkPublishSerializer,
    HomeworkSubmissionReviewSerializer,
    HomeworkSubmissionSerializer,
    HomeworkSubmissionWriteSerializer,
)
from apps.users.models import StudentProfile, User
from apps.users.permissions import IsStudent


def _teacher_course(view, slug):
    course = get_course_for_request(view, slug)
    ensure_can_modify_course(view.request.user, course)
    return course


def _can_manage_assignment(user, assignment: HomeworkAssignment) -> bool:
    if user.role == User.RoleChoices.ADMINISTRATOR:
        return True
    return assignment.created_by_id == user.id


def _teacher_assignment(view, slug: str, assignment_id: int) -> HomeworkAssignment:
    assignment = get_object_or_404(
        HomeworkAssignment.objects.filter(course__slug=slug, course__is_deleted=False)
        .select_related("course", "module", "lesson", "test", "test__module", "created_by")
        .prefetch_related("test__questions", "recipients__enrollment__student_profile__user"),
        pk=assignment_id,
    )
    if not _can_manage_assignment(view.request.user, assignment):
        raise PermissionDenied("Only the teacher who sent this homework can manage it.")
    return assignment


def _best_test_attempt(
    assignment: HomeworkAssignment, enrollment: Enrollment
) -> TestAttempt | None:
    if assignment.test_id is None:
        return None
    return (
        TestAttempt.objects.filter(
            student_profile=enrollment.student_profile,
            test=assignment.test,
        )
        .select_related("student_profile", "test")
        .order_by("-score", "-submitted_at", "-attempt_number")
        .first()
    )


def _student_enrollment(user) -> Enrollment:
    try:
        profile = user.student_profile
    except StudentProfile.DoesNotExist as exc:
        raise PermissionDenied("Student profile is required.") from exc

    enrollment = Enrollment.objects.with_active_access().filter(
        student_profile=profile,
    )
    return enrollment


def _student_assignment_and_enrollment(user, assignment_id: int):
    active_enrollments = _student_enrollment(user)
    recipient = get_object_or_404(
        HomeworkAssignmentRecipient.objects.select_related("assignment", "enrollment"),
        assignment_id=assignment_id,
        enrollment__in=active_enrollments,
        assignment__status=HomeworkAssignment.StatusChoices.PUBLISHED,
    )
    return recipient.assignment, recipient.enrollment


@extend_schema(tags=["Homework"])
class HomeworkAssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = HomeworkAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def _get_course(self):
        return _teacher_course(self, self.kwargs["slug"])

    def get_queryset(self):
        queryset = (
            HomeworkAssignment.objects.filter(course=self._get_course())
            .select_related(
                "course",
                "module",
                "lesson",
                "test",
                "test__module",
                "source_assignment",
                "created_by",
            )
            .prefetch_related(
                "attachments",
                "test__questions",
                "recipients__enrollment__student_profile__user",
                "submissions__attachments",
                "submissions__enrollment__student_profile__user",
                "submissions__best_test_attempt__test",
            )
            .annotate(recipients_count=Count("recipients"))
        )
        if self.request.user.role != User.RoleChoices.ADMINISTRATOR:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["course"] = self._get_course()
        return context

    def perform_create(self, serializer):
        serializer.save(course=self._get_course(), created_by=self.request.user)


@extend_schema(tags=["Homework"])
class HomeworkAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        payload = HomeworkAssignmentSerializer(assignment, context={"request": request}).data
        payload["submissions"] = HomeworkSubmissionSerializer(
            assignment.submissions.select_related(
                "enrollment__student_profile__user",
                "best_test_attempt__student_profile",
                "best_test_attempt__test",
            ).prefetch_related("attachments"),
            many=True,
            context={"request": request},
        ).data
        return Response(payload)

    def patch(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status != HomeworkAssignment.StatusChoices.DRAFT:
            return Response(
                {"detail": "Only draft assignments can be edited."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = HomeworkAssignmentSerializer(
            assignment,
            data=request.data,
            partial=True,
            context={"course": assignment.course, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(HomeworkAssignmentSerializer(assignment, context={"request": request}).data)

    def delete(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status != HomeworkAssignment.StatusChoices.DRAFT:
            return Response(
                {"detail": "Only draft assignments can be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Homework"])
class HomeworkAvailableRecipientsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        course = _teacher_course(self, slug)
        recipients = (
            Enrollment.objects.with_active_access()
            .exclude_completed()
            .filter(course=course)
            .select_related("student_profile__user", "delivery_format")
            .prefetch_related("cohort_memberships__cohort")
            .order_by("student_profile__user__last_name", "student_profile__user__first_name")
        )
        return Response(HomeworkAvailableRecipientSerializer(recipients, many=True).data)


@extend_schema(tags=["Homework"])
class HomeworkAssignmentPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status == HomeworkAssignment.StatusChoices.CLOSED:
            return Response(
                {"detail": "Closed homework cannot be published."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = HomeworkPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        explicit_ids = list(dict.fromkeys(serializer.validated_data["enrollment_ids"]))
        cohort_ids = list(dict.fromkeys(serializer.validated_data["cohort_ids"]))
        delivery_format_ids = list(dict.fromkeys(serializer.validated_data["delivery_format_ids"]))

        if cohort_ids:
            valid_cohort_count = Cohort.objects.filter(
                course=assignment.course,
                pk__in=cohort_ids,
            ).count()
            if valid_cohort_count != len(cohort_ids):
                return Response(
                    {"cohort_ids": "Each cohort must belong to this course."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if delivery_format_ids:
            valid_format_count = CourseDeliveryFormat.objects.filter(
                course=assignment.course,
                pk__in=delivery_format_ids,
            ).count()
            if valid_format_count != len(delivery_format_ids):
                return Response(
                    {"delivery_format_ids": "Each delivery format must belong to this course."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        recipient_ids = set(explicit_ids)
        if cohort_ids:
            recipient_ids.update(
                Enrollment.objects.with_active_access()
                .filter(course=assignment.course, cohort_memberships__cohort_id__in=cohort_ids)
                .values_list("id", flat=True)
            )
        if delivery_format_ids:
            recipient_ids.update(
                Enrollment.objects.with_active_access()
                .filter(course=assignment.course, delivery_format_id__in=delivery_format_ids)
                .values_list("id", flat=True)
            )

        recipients = list(
            Enrollment.objects.with_active_access().filter(
                course=assignment.course,
                pk__in=recipient_ids,
            )
        )
        if len(recipients) != len(recipient_ids):
            return Response(
                {"enrollment_ids": "Each recipient must have active access to this course."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not recipients:
            return Response(
                {"detail": "The selected group has no active students."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_ids = [enrollment.id for enrollment in recipients]

        with transaction.atomic():
            HomeworkAssignmentRecipient.objects.filter(assignment=assignment).exclude(
                enrollment_id__in=recipient_ids,
            ).delete()
            HomeworkAssignmentRecipient.objects.bulk_create(
                [
                    HomeworkAssignmentRecipient(assignment=assignment, enrollment=enrollment)
                    for enrollment in recipients
                ],
                ignore_conflicts=True,
            )
            assignment.status = HomeworkAssignment.StatusChoices.PUBLISHED
            assignment.published_at = assignment.published_at or timezone.now()
            assignment.closed_at = None
            assignment.save(update_fields=["status", "published_at", "closed_at", "updated_at"])

        assignment.refresh_from_db()
        return Response(HomeworkAssignmentSerializer(assignment, context={"request": request}).data)


@extend_schema(tags=["Homework"])
class HomeworkAssignmentCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status != HomeworkAssignment.StatusChoices.PUBLISHED:
            return Response(
                {"detail": "Only published homework can be closed."},
                status=status.HTTP_409_CONFLICT,
            )
        assignment.status = HomeworkAssignment.StatusChoices.CLOSED
        assignment.closed_at = timezone.now()
        assignment.save(update_fields=["status", "closed_at", "updated_at"])
        return Response(HomeworkAssignmentSerializer(assignment, context={"request": request}).data)


@extend_schema(tags=["Homework"])
class HomeworkAssignmentAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, assignment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status != HomeworkAssignment.StatusChoices.DRAFT:
            return Response(
                {"detail": "Files can only be changed while homework is a draft."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = HomeworkFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]
        attachment = HomeworkAssignmentAttachment.objects.create(
            assignment=assignment,
            file=uploaded_file,
            original_name=uploaded_file.name[:255],
            uploaded_by=request.user,
        )
        return Response(
            HomeworkAssignmentAttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Homework"])
class HomeworkAssignmentAttachmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug: str, assignment_id: int, attachment_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        if assignment.status != HomeworkAssignment.StatusChoices.DRAFT:
            return Response(
                {"detail": "Files can only be changed while homework is a draft."},
                status=status.HTTP_409_CONFLICT,
            )
        attachment = get_object_or_404(
            HomeworkAssignmentAttachment,
            pk=attachment_id,
            assignment=assignment,
        )
        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Homework"])
class StudentHomeworkListView(generics.ListAPIView):
    serializer_class = HomeworkAssignmentSerializer
    permission_classes = [IsStudent]
    pagination_class = None

    def get_queryset(self):
        active_enrollments = _student_enrollment(self.request.user)
        return (
            HomeworkAssignment.objects.filter(
                status=HomeworkAssignment.StatusChoices.PUBLISHED,
                recipients__enrollment__in=active_enrollments,
            )
            .select_related("course", "module", "lesson", "test", "test__module")
            .prefetch_related("attachments", "test__questions")
            .distinct()
            .order_by("due_at", "-published_at")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context["student_profile"] = self.request.user.student_profile
        except StudentProfile.DoesNotExist:
            context["student_profile"] = None
        context["hide_answers"] = True
        return context


@extend_schema(tags=["Homework"])
class StudentHomeworkSubmissionView(APIView):
    permission_classes = [IsStudent]

    def _get_assignment_and_enrollment(self, request, assignment_id: int):
        return _student_assignment_and_enrollment(request.user, assignment_id)

    def get(self, request, assignment_id: int):
        assignment, enrollment = self._get_assignment_and_enrollment(request, assignment_id)
        submission = HomeworkSubmission.objects.filter(
            assignment=assignment,
            enrollment=enrollment,
        ).first()
        if submission is None:
            return Response({"detail": "No submission yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(HomeworkSubmissionSerializer(submission, context={"request": request}).data)

    def post(self, request, assignment_id: int):
        assignment, enrollment = self._get_assignment_and_enrollment(request, assignment_id)
        serializer = HomeworkSubmissionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data["content"]
        best_attempt = _best_test_attempt(assignment, enrollment)

        if assignment.test_id is not None and best_attempt is None:
            return Response(
                {"detail": "Complete the test before submitting this homework."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_submission = HomeworkSubmission.objects.filter(
            assignment=assignment,
            enrollment=enrollment,
        ).first()
        if (
            existing_submission
            and existing_submission.status == HomeworkSubmission.StatusChoices.RETRIEVED
        ):
            return Response(
                {"detail": "This homework review is currently retrieved by the teacher."},
                status=status.HTTP_409_CONFLICT,
            )
        has_attachments = (
            existing_submission is not None and existing_submission.attachments.exists()
        )
        if not content and not has_attachments and best_attempt is None:
            return Response(
                {"detail": "Add text, attach a file, or complete the test before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission, _ = HomeworkSubmission.objects.update_or_create(
            assignment=assignment,
            enrollment=enrollment,
            defaults={
                "content": content,
                "best_test_attempt": best_attempt,
                "status": HomeworkSubmission.StatusChoices.SUBMITTED,
                "score": None,
                "feedback": "",
                "reviewed_at": None,
                "submitted_at": timezone.now(),
            },
        )
        return Response(
            HomeworkSubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Homework"])
class StudentHomeworkSubmissionAttachmentView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, assignment_id: int):
        assignment, enrollment = _student_assignment_and_enrollment(request.user, assignment_id)
        serializer = HomeworkFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission, _ = HomeworkSubmission.objects.get_or_create(
            assignment=assignment,
            enrollment=enrollment,
            defaults={"content": ""},
        )
        if submission.status == HomeworkSubmission.StatusChoices.RETRIEVED:
            return Response(
                {"detail": "This homework review is currently retrieved by the teacher."},
                status=status.HTTP_409_CONFLICT,
            )
        if submission.status == HomeworkSubmission.StatusChoices.REVIEWED:
            submission.status = HomeworkSubmission.StatusChoices.SUBMITTED
            submission.score = None
            submission.feedback = ""
            submission.reviewed_at = None
            submission.submitted_at = timezone.now()
            submission.save(
                update_fields=[
                    "status",
                    "score",
                    "feedback",
                    "reviewed_at",
                    "submitted_at",
                    "updated_at",
                ]
            )
        uploaded_file = serializer.validated_data["file"]
        HomeworkSubmissionAttachment.objects.create(
            submission=submission,
            file=uploaded_file,
            original_name=uploaded_file.name[:255],
        )
        return Response(
            HomeworkSubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Homework"])
class StudentHomeworkSubmissionAttachmentDetailView(APIView):
    permission_classes = [IsStudent]

    def delete(self, request, assignment_id: int, attachment_id: int):
        assignment, enrollment = _student_assignment_and_enrollment(request.user, assignment_id)
        attachment = get_object_or_404(
            HomeworkSubmissionAttachment.objects.select_related("submission"),
            pk=attachment_id,
            submission__assignment=assignment,
            submission__enrollment=enrollment,
        )
        if attachment.submission.status == HomeworkSubmission.StatusChoices.RETRIEVED:
            return Response(
                {"detail": "This homework review is currently retrieved by the teacher."},
                status=status.HTTP_409_CONFLICT,
            )
        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Homework"])
class HomeworkSubmissionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug: str, assignment_id: int, submission_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        submission = get_object_or_404(
            HomeworkSubmission.objects.select_related("enrollment__student_profile__user"),
            pk=submission_id,
            assignment=assignment,
        )
        if submission.status == HomeworkSubmission.StatusChoices.REVIEWED:
            return Response(
                {"detail": "Retrieve the returned homework before editing the review."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = HomeworkSubmissionReviewSerializer(
            data=request.data,
            partial=True,
            context={"assignment": assignment},
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(submission, field, value)
        submission.status = HomeworkSubmission.StatusChoices.REVIEWED
        submission.reviewed_at = timezone.now()
        submission.save()
        return Response(HomeworkSubmissionSerializer(submission, context={"request": request}).data)


@extend_schema(tags=["Homework"])
class HomeworkSubmissionRetrieveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, assignment_id: int, submission_id: int):
        assignment = _teacher_assignment(self, slug, assignment_id)
        submission = get_object_or_404(
            HomeworkSubmission.objects.select_related("enrollment__student_profile__user"),
            pk=submission_id,
            assignment=assignment,
        )
        if submission.status != HomeworkSubmission.StatusChoices.REVIEWED:
            return Response(
                {"detail": "Only returned reviewed homework can be retrieved."},
                status=status.HTTP_409_CONFLICT,
            )
        submission.status = HomeworkSubmission.StatusChoices.RETRIEVED
        submission.reviewed_at = None
        submission.save(update_fields=["status", "reviewed_at", "updated_at"])
        return Response(HomeworkSubmissionSerializer(submission, context={"request": request}).data)


def _bucket_scores(qs, period: str) -> tuple[list[dict], float]:
    """Average reviewed homework score per week (last 6) or per month (current year)."""
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
        trunc = TruncMonth("reviewed_at")
    else:
        this_week = today - timedelta(days=today.weekday())
        buckets = [this_week - timedelta(weeks=5 - i) for i in range(6)]
        labels = [f"Week {i + 1}" for i in range(6)]
        trunc = TruncWeek("reviewed_at")

    windowed = qs.filter(reviewed_at__date__gte=buckets[0])
    grouped = {
        row["bucket"].date(): row["avg"]
        for row in windowed.annotate(bucket=trunc).values("bucket").annotate(avg=Avg("score"))
    }
    points = [
        {
            "label": label,
            "date": bucket.isoformat(),
            "period": period,
            "value": round(grouped.get(bucket, 0) or 0, 1),
        }
        for bucket, label in zip(buckets, labels, strict=True)
    ]
    overall = windowed.aggregate(avg=Avg("score"))["avg"]
    return points, round(overall, 1) if overall else 0


@extend_schema(tags=["Homework"])
class HomeworkGrowthView(APIView):
    """GET /homework/growth/: average reviewed homework score over time, for the dashboard "Growth" widget."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period", "weekly")
        course_slug = request.query_params.get("course")
        student_id = request.query_params.get("student_id")
        user = request.user

        if user.role == User.RoleChoices.STUDENT:
            enrollments = _student_enrollment(user)
            courses = Course.objects.filter(id__in=enrollments.values("course_id")).distinct()
            if course_slug:
                enrollments = enrollments.filter(course__slug=course_slug)
            qs = HomeworkSubmission.objects.filter(
                enrollment__in=enrollments,
                score__isnull=False,
                reviewed_at__isnull=False,
            )
        elif student_id and user.role in {
            User.RoleChoices.TEACHER,
            User.RoleChoices.ADMINISTRATOR,
        }:
            try:
                numeric_student_id = int(student_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "student_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            enrollments = Enrollment.objects.filter(
                student_profile__user_id=numeric_student_id,
            )
            if user.role == User.RoleChoices.TEACHER:
                enrollments = enrollments.filter(course__teacher_profile__user=user)
            courses = Course.objects.filter(id__in=enrollments.values("course_id")).distinct()
            if course_slug:
                enrollments = enrollments.filter(course__slug=course_slug)
            qs = HomeworkSubmission.objects.filter(
                enrollment__in=enrollments,
                score__isnull=False,
                reviewed_at__isnull=False,
            )
        else:
            # Teachers get a dedicated enrollment-count metric instead
            # (GET /enrollments/growth/, apps/enrollments/views/EnrollmentGrowthView.py).
            return Response({"average": 0, "points": [], "courses": []})

        points, average = _bucket_scores(qs, period)
        return Response(
            {
                "average": average,
                "points": points,
                "courses": [{"slug": c.slug, "title": c.title} for c in courses],
            }
        )
