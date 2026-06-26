from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Cohort, CourseDeliveryFormat
from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
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
    HomeworkSubmissionAttachmentSerializer,
    HomeworkSubmissionReviewSerializer,
    HomeworkSubmissionSerializer,
    HomeworkSubmissionWriteSerializer,
)
from apps.users.models import StudentProfile
from apps.users.permissions import IsStudent


def _teacher_course(view, slug):
    course = get_course_for_request(view, slug)
    ensure_can_modify_course(view.request.user, course)
    return course


def _teacher_assignment(view, slug: str, assignment_id: int) -> HomeworkAssignment:
    course = _teacher_course(view, slug)
    return get_object_or_404(
        HomeworkAssignment.objects.filter(course=course)
        .select_related("course", "module", "lesson", "test", "test__module")
        .prefetch_related("test__questions", "recipients__enrollment__student_profile__user"),
        pk=assignment_id,
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
        return (
            HomeworkAssignment.objects.filter(course=self._get_course())
            .select_related("course", "module", "lesson", "test", "test__module", "source_assignment")
            .prefetch_related(
                "attachments",
                "test__questions",
                "recipients__enrollment__student_profile__user",
                "submissions__attachments",
                "submissions__enrollment__student_profile__user",
            )
            .annotate(recipients_count=Count("recipients"))
        )

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
        submission, _ = HomeworkSubmission.objects.update_or_create(
            assignment=assignment,
            enrollment=enrollment,
            defaults={
                "content": serializer.validated_data["content"],
                "status": HomeworkSubmission.StatusChoices.SUBMITTED,
                "score": None,
                "feedback": "",
                "reviewed_at": None,
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
