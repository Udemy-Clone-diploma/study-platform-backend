from django.db import transaction
from rest_framework import serializers

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.enrollments.serializers import (
    EnrollmentCreateSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
)
from apps.users.models import StudentProfile, User


class EnrollmentService:
    @staticmethod
    def get_base_queryset():
        return Enrollment.objects.select_related(
            "student_profile__user",
            "course",
            "course__teacher_profile__user",
        )

    @classmethod
    def get_visible_enrollments_queryset(cls, user: User, base_queryset=None):
        queryset = base_queryset if base_queryset is not None else cls.get_base_queryset()

        if not user or not user.is_authenticated:
            return queryset.none()

        if user.role in (
            User.RoleChoices.ADMINISTRATOR,
            User.RoleChoices.MODERATOR,
        ):
            return queryset

        if user.role == User.RoleChoices.TEACHER:
            return queryset.filter(course__teacher_profile__user_id=user.id)

        if user.role == User.RoleChoices.STUDENT:
            return queryset.filter(student_profile__user_id=user.id)

        return queryset.none()

    @staticmethod
    def serialize_enrollment(
        enrollment: Enrollment,
        context: dict | None = None,
    ) -> dict:
        return EnrollmentSerializer(enrollment, context=context or {}).data

    @staticmethod
    def validate_create_data(data: dict, context: dict | None = None) -> dict:
        serializer = EnrollmentCreateSerializer(data=data, context=context or {})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def validate_update_data(
        data: dict,
        context: dict | None = None,
        partial: bool = True,
    ) -> dict:
        serializer = EnrollmentUpdateSerializer(
            data=data,
            context=context or {},
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @classmethod
    def create_enrollment_from_data(
        cls,
        data: dict,
        request_user: User,
        context: dict | None = None,
    ) -> dict:
        validated_data = cls.validate_create_data(data, context=context)
        enrollment = cls.create_enrollment(validated_data, request_user)
        return cls.serialize_enrollment(enrollment, context=context)

    @classmethod
    def update_enrollment_from_data(
        cls,
        enrollment: Enrollment,
        data: dict,
        context: dict | None = None,
        partial: bool = True,
    ) -> dict:
        validated_data = cls.validate_update_data(
            data,
            context=context,
            partial=partial,
        )
        enrollment = cls.update_enrollment(enrollment, validated_data)
        return cls.serialize_enrollment(enrollment, context=context)

    @staticmethod
    def _student_profile_for_user(user: User) -> StudentProfile:
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"student_profile_id": "Student profile is required for enrollment."}
            ) from exc

    @classmethod
    def _resolve_student_profile(
        cls,
        request_user: User,
        requested_profile: StudentProfile | None = None,
    ) -> StudentProfile:
        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            if requested_profile is None:
                raise serializers.ValidationError(
                    {"student_profile_id": "This field is required for administrators."}
                )
            return requested_profile

        if request_user.role == User.RoleChoices.STUDENT:
            return cls._student_profile_for_user(request_user)

        raise serializers.ValidationError(
            {"detail": "Only students and administrators can create enrollments."}
        )

    @staticmethod
    def _validate_course_is_available(course: Course, request_user: User) -> None:
        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            return
        if course.status != Course.StatusChoices.PUBLISHED or course.is_deleted:
            raise serializers.ValidationError(
                {"course_id": "Only published courses are available for enrollment."}
            )

    @classmethod
    @transaction.atomic
    def create_enrollment(
        cls,
        validated_data: dict,
        request_user: User,
    ) -> Enrollment:
        course = validated_data["course"]
        student_profile = cls._resolve_student_profile(
            request_user,
            validated_data.get("student_profile"),
        )
        cls._validate_course_is_available(course, request_user)

        if Enrollment.objects.filter(
            student_profile=student_profile,
            course=course,
        ).exists():
            raise serializers.ValidationError(
                {"course_id": "Student is already enrolled in this course."}
            )

        enrollment_data = {
            "student_profile": student_profile,
            "course": course,
        }

        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            enrollment_data.update(
                {
                    "order_id": validated_data.get("order_id"),
                    "access_status": validated_data.get(
                        "access_status",
                        Enrollment.AccessStatusChoices.ACTIVE,
                    ),
                    "access_until": validated_data.get("access_until"),
                }
            )

        return Enrollment.objects.create(**enrollment_data)

    @staticmethod
    @transaction.atomic
    def update_enrollment(enrollment: Enrollment, validated_data: dict) -> Enrollment:
        access_until = validated_data.get("access_until", enrollment.access_until)
        if access_until is not None and access_until < enrollment.access_granted_at:
            raise serializers.ValidationError(
                {"access_until": "Access end date cannot be before access grant date."}
            )

        for field in ("order_id", "access_status", "access_until"):
            if field in validated_data:
                setattr(enrollment, field, validated_data[field])

        enrollment.save()
        return enrollment

    @staticmethod
    @transaction.atomic
    def revoke_enrollment(enrollment: Enrollment) -> None:
        enrollment.revoke()

    @staticmethod
    def student_has_course_access(student_profile: StudentProfile, course: Course) -> bool:
        return Enrollment.objects.with_active_access().filter(
            student_profile=student_profile,
            course=course,
        ).exists()
