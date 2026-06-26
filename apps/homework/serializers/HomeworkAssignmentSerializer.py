from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.curriculum.models import Lesson, Module, Test
from apps.curriculum.serializers import TestSerializer
from apps.enrollments.models import Enrollment
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentAttachment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
    HomeworkSubmissionAttachment,
)
from apps.users.models import StudentProfile


MAX_HOMEWORK_ATTACHMENT_BYTES = 25 * 1024 * 1024


class HomeworkFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)

    def validate_file(self, uploaded_file):
        if uploaded_file.size > MAX_HOMEWORK_ATTACHMENT_BYTES:
            raise serializers.ValidationError("A homework attachment cannot exceed 25 MB.")
        return uploaded_file


class HomeworkAssignmentAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = HomeworkAssignmentAttachment
        fields = ["id", "original_name", "url", "created_at"]

    def get_url(self, obj):
        return absolute_media_url(obj.file, self.context.get("request"))


class HomeworkSubmissionAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = HomeworkSubmissionAttachment
        fields = ["id", "original_name", "url", "created_at"]

    def get_url(self, obj):
        return absolute_media_url(obj.file, self.context.get("request"))


class HomeworkRecipientSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(read_only=True)
    student_email = serializers.EmailField(source="enrollment.student_profile.user.email", read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = HomeworkAssignmentRecipient
        fields = ["id", "enrollment_id", "student_email", "student_name", "assigned_at"]

    def get_student_name(self, obj) -> str:
        return obj.enrollment.student_profile.user.get_full_name()


class HomeworkAvailableRecipientSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student_profile.user.email", read_only=True)
    student_name = serializers.SerializerMethodField()
    delivery_format_id = serializers.IntegerField(read_only=True)
    delivery_format_type = serializers.CharField(source="delivery_format.format_type", read_only=True)
    cohort_ids = serializers.SerializerMethodField()
    cohort_names = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student_email",
            "student_name",
            "delivery_format_id",
            "delivery_format_type",
            "cohort_ids",
            "cohort_names",
        ]

    def get_student_name(self, obj) -> str:
        return obj.student_profile.user.get_full_name()

    def get_cohort_ids(self, obj) -> list[int]:
        return [membership.cohort_id for membership in obj.cohort_memberships.all()]

    def get_cohort_names(self, obj) -> list[str]:
        return [
            membership.cohort.name or str(membership.cohort)
            for membership in obj.cohort_memberships.all()
        ]


class HomeworkSubmissionSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(read_only=True)
    student_email = serializers.EmailField(source="enrollment.student_profile.user.email", read_only=True)
    student_name = serializers.SerializerMethodField()
    attachments = HomeworkSubmissionAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = HomeworkSubmission
        fields = [
            "id", "enrollment_id", "student_email", "student_name", "content",
            "attachments", "status", "score", "feedback", "submitted_at", "reviewed_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "enrollment_id", "student_email", "student_name", "status",
            "score", "feedback", "submitted_at", "reviewed_at", "updated_at",
        ]

    def get_student_name(self, obj) -> str:
        return obj.enrollment.student_profile.user.get_full_name()


class HomeworkAssignmentSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(source="course.id", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_image = serializers.SerializerMethodField()
    module_title = serializers.CharField(source="module.title", read_only=True, allow_null=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True, allow_null=True)
    source_assignment = serializers.PrimaryKeyRelatedField(
        queryset=HomeworkAssignment.objects.all(),
        allow_null=True,
        required=False,
    )
    test = serializers.PrimaryKeyRelatedField(
        queryset=Test.objects.all(),
        allow_null=True,
        required=False,
    )
    test_detail = TestSerializer(source="test", read_only=True)
    lesson = serializers.PrimaryKeyRelatedField(
        queryset=Lesson.objects.all(),
        allow_null=True,
        required=False,
    )
    module = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.all(),
        allow_null=True,
        required=False,
    )
    recipients = serializers.SerializerMethodField()
    recipients_count = serializers.IntegerField(read_only=True)
    my_submission = serializers.SerializerMethodField()
    teacher_submissions = serializers.SerializerMethodField()
    attachments = HomeworkAssignmentAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = HomeworkAssignment
        fields = [
            "id",
            "course_id",
            "course_title",
            "course_image",
            "source_assignment",
            "module",
            "module_title",
            "lesson",
            "lesson_title",
            "test",
            "test_detail",
            "title",
            "description",
            "due_at",
            "max_score",
            "status",
            "published_at",
            "closed_at",
            "attachments",
            "recipients",
            "recipients_count",
            "my_submission",
            "teacher_submissions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "course_id", "status", "published_at", "closed_at",
            "course_title", "course_image", "module_title", "lesson_title", "test_detail", "attachments",
            "recipients", "recipients_count", "my_submission", "teacher_submissions",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "max_score": {"min_value": 1},
            "title": {"required": False, "allow_blank": False},
            "description": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs: dict) -> dict:
        course = self.context["course"]
        source_assignment: HomeworkAssignment | None = attrs.get("source_assignment")
        module: Module | None = attrs.get("module")
        lesson: Lesson | None = attrs.get("lesson")
        test: Test | None = attrs.get("test")
        errors = {}

        effective_test = test if "test" in attrs else getattr(self.instance, "test", None)
        effective_description = (
            attrs["description"]
            if "description" in attrs
            else getattr(self.instance, "description", "")
        )

        if self.instance is None and source_assignment is None:
            if not attrs.get("title"):
                errors["title"] = "This field is required unless source_assignment is provided."

        if source_assignment is None and effective_test is None and not effective_description:
            errors["description"] = "This field is required unless a test is selected."

        if source_assignment is not None and source_assignment.course_id != course.id:
            errors["source_assignment"] = "The source homework must belong to the selected course."

        if module is not None and module.course_id != course.id:
            errors["module"] = "The module must belong to the selected course."

        if lesson is not None:
            if lesson.module.course_id != course.id:
                errors["lesson"] = "The lesson must belong to the selected course."
            elif module is not None and lesson.module_id != module.id:
                errors["lesson"] = "The lesson must belong to the selected module."

        if test is not None:
            if test.module.course_id != course.id:
                errors["test"] = "The test must belong to the selected course."
            elif module is not None and test.module_id != module.id:
                errors["test"] = "The test must belong to the selected module."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        source_assignment = validated_data.get("source_assignment")
        if source_assignment is not None:
            for field in ("title", "description", "module", "lesson", "test", "max_score"):
                if validated_data.get(field) in (None, ""):
                    validated_data[field] = getattr(source_assignment, field)
        return super().create(validated_data)

    def get_course_image(self, obj) -> str | None:
        return absolute_media_url(obj.course.image, self.context.get("request"))

    def get_my_submission(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        try:
            profile = request.user.student_profile
        except StudentProfile.DoesNotExist:
            return None
        submission = HomeworkSubmission.objects.filter(
            assignment=obj,
            enrollment__student_profile=profile,
        ).select_related("enrollment__student_profile__user").prefetch_related("attachments").first()
        return (
            HomeworkSubmissionSerializer(submission, context=self.context).data
            if submission
            else None
        )

    def get_recipients(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return []
        is_owner = obj.course.teacher_profile.user_id == request.user.id
        is_admin = request.user.role == "administrator"
        if not (is_owner or is_admin):
            return []
        recipients = obj.recipients.select_related("enrollment__student_profile__user")
        return HomeworkRecipientSerializer(recipients, many=True).data

    def get_teacher_submissions(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return []
        is_owner = obj.course.teacher_profile.user_id == request.user.id
        is_admin = request.user.role == "administrator"
        if not (is_owner or is_admin):
            return []
        submissions = obj.submissions.select_related(
            "enrollment__student_profile__user",
        ).prefetch_related("attachments")
        return HomeworkSubmissionSerializer(submissions, many=True, context=self.context).data


class HomeworkPublishSerializer(serializers.Serializer):
    enrollment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    cohort_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )
    delivery_format_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate(self, attrs: dict) -> dict:
        if not (
            attrs.get("enrollment_ids")
            or attrs.get("cohort_ids")
            or attrs.get("delivery_format_ids")
        ):
            raise serializers.ValidationError(
                "At least one enrollment, cohort, or delivery format must be selected."
            )
        return attrs


class HomeworkSubmissionWriteSerializer(serializers.Serializer):
    content = serializers.CharField(trim_whitespace=True, allow_blank=False)


class HomeworkSubmissionReviewSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    feedback = serializers.CharField(required=False, allow_blank=True)

    def validate_score(self, value):
        assignment: HomeworkAssignment = self.context["assignment"]
        if value is not None and assignment.max_score is not None and value > assignment.max_score:
            raise serializers.ValidationError("Score cannot exceed the assignment maximum.")
        return value
