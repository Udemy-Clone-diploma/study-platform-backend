from decimal import Decimal

from django.db import transaction
from django.utils.timezone import now as tz_now

from apps.cart.models import CartItem
from apps.courses.models import Course, PricingPlan
from apps.schedule.exceptions import SlotAlreadyBookedError, SlotNotAvailableError
from apps.enrollments.exceptions import (
    CourseNotEnrollableError,
    DuplicateEnrollmentError,
    EnrollmentRoleError,
    FreeEnrollmentUnavailableError,
    InvalidAccessWindowError,
    StudentProfileRequiredError,
)
from apps.enrollments.models import Enrollment
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
    def _student_profile_for_user(user: User) -> StudentProfile:
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist as exc:
            raise StudentProfileRequiredError(
                "Student profile is required for enrollment."
            ) from exc

    @classmethod
    def _resolve_student_profile(
        cls,
        request_user: User,
        requested_profile: StudentProfile | None = None,
    ) -> StudentProfile:
        if request_user.role != User.RoleChoices.ADMINISTRATOR:
            raise EnrollmentRoleError(
                "Only administrators can create enrollments manually."
            )
        if requested_profile is None:
            raise StudentProfileRequiredError(
                "student_profile_id is required for administrators."
            )
        return requested_profile

    @staticmethod
    def _validate_course_is_available(course: Course, request_user: User) -> None:
        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            return
        if course.status != Course.StatusChoices.PUBLISHED or course.is_deleted:
            raise CourseNotEnrollableError(
                "Only published courses are available for enrollment."
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

        delivery_format = validated_data.get("delivery_format")
        if (
            delivery_format
            and delivery_format.enrollment_deadline
            and request_user.role != User.RoleChoices.ADMINISTRATOR
            and delivery_format.enrollment_deadline < tz_now().date()
        ):
            raise CourseNotEnrollableError("Enrollment for this format has closed.")

        if Enrollment.objects.filter(
            student_profile=student_profile,
            course=course,
        ).exists():
            raise DuplicateEnrollmentError(
                "Student is already enrolled in this course."
            )

        enrollment_data = {
            "student_profile": student_profile,
            "course": course,
            "delivery_format": validated_data.get("delivery_format"),
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

        enrollment = Enrollment.objects.create(**enrollment_data)

        # If a schedule_slot_id was supplied (individual delivery format),
        # book the slot atomically so no other student can claim it.
        schedule_slot_id = validated_data.get("schedule_slot_id")
        if schedule_slot_id is not None:
            cls._book_schedule_slot(enrollment, schedule_slot_id)

        return enrollment

    @staticmethod
    def _book_schedule_slot(enrollment: "Enrollment", slot_id: int) -> None:
        from apps.schedule.models import ScheduleSlot
        from apps.schedule.services import ScheduleService

        try:
            slot = ScheduleSlot.objects.select_for_update().get(
                pk=slot_id,
                delivery_format__course=enrollment.course,
            )
        except ScheduleSlot.DoesNotExist:
            raise SlotNotAvailableError(
                "The requested schedule slot does not exist or does not belong to this course."
            )

        ScheduleService.book_slot(slot, enrollment)

    @classmethod
    @transaction.atomic
    def enroll_in_free_course(
        cls,
        user: User,
        course: Course,
    ) -> tuple[Enrollment, bool]:
        """Grant student access only when the published course has a zero-price plan."""
        if user.role != User.RoleChoices.STUDENT:
            raise EnrollmentRoleError("Only students can enroll in free courses.")
        if course.status != Course.StatusChoices.PUBLISHED or course.is_deleted:
            raise CourseNotEnrollableError("Only published courses are available for enrollment.")
        if not PricingPlan.objects.filter(
            delivery_format__course=course,
            price=Decimal("0.00"),
        ).exists():
            raise FreeEnrollmentUnavailableError("This course is not available for free enrollment.")

        student_profile = cls._student_profile_for_user(user)
        enrollment, created = Enrollment.all_objects.get_or_create(
            student_profile=student_profile,
            course=course,
            defaults={
                "access_status": Enrollment.AccessStatusChoices.ACTIVE,
                "access_until": None,
                "order_id": None,
            },
        )

        if not created and (enrollment.is_deleted or not enrollment.has_active_access):
            enrollment.access_status = Enrollment.AccessStatusChoices.ACTIVE
            enrollment.access_until = None
            enrollment.order_id = None
            enrollment.is_deleted = False
            enrollment.save(
                update_fields=["access_status", "access_until", "order_id", "is_deleted"]
            )

        CartItem.objects.filter(
            cart__student_profile=student_profile,
            course=course,
        ).delete()
        return enrollment, created

    @staticmethod
    @transaction.atomic
    def update_enrollment(enrollment: Enrollment, validated_data: dict) -> Enrollment:
        access_until = validated_data.get("access_until", enrollment.access_until)
        if access_until is not None and access_until < enrollment.access_granted_at:
            raise InvalidAccessWindowError(
                "Access end date cannot be before access grant date."
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

    @classmethod
    def is_enrolled(cls, user, course: Course) -> bool:
        """Convenience wrapper: does this user have an active enrollment?

        Returns False for anonymous users, non-students, and students without
        a profile. Otherwise delegates to ``student_has_course_access``.
        """
        if not user or not user.is_authenticated:
            return False
        if user.role != User.RoleChoices.STUDENT:
            return False
        try:
            student_profile = user.student_profile
        except StudentProfile.DoesNotExist:
            return False
        return cls.student_has_course_access(student_profile, course)
