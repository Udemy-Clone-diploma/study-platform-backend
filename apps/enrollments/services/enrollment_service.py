from decimal import Decimal

from django.db import transaction
from django.utils.timezone import now as tz_now

from apps.cart.models import CartItem
from apps.courses.models import Course, CourseDeliveryFormat, PricingPlan
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

    @staticmethod
    def apply_delivery_setup(
        enrollment: "Enrollment",
        cohort_id: int | None = None,
        schedule_slot_ids: list[int] | None = None,
    ) -> None:
        """Format-specific side effects also used by the paid-checkout webhook
        path (`WebhookService._grant_enrollments`): cohort membership for group,
        slot booking for individual/scheduled. Kept here as the single source of
        truth so free and paid enrollment can never drift apart."""
        if cohort_id is not None:
            from apps.courses.models import CohortMember

            CohortMember.objects.get_or_create(cohort_id=cohort_id, enrollment=enrollment)

        if schedule_slot_ids:
            from apps.schedule.models import ScheduleSlot
            from apps.schedule.services import ScheduleService

            slots = ScheduleSlot.objects.select_for_update().filter(
                pk__in=schedule_slot_ids, delivery_format__course=enrollment.course,
            )
            for slot in slots:
                try:
                    ScheduleService.book_slot(slot, enrollment)
                except SlotAlreadyBookedError:
                    continue

    @classmethod
    @transaction.atomic
    def enroll_in_free_course(
        cls,
        user: User,
        course: Course,
        delivery_format_id: int | None = None,
        pricing_plan_id: int | None = None,
        cohort_id: int | None = None,
        schedule_slot_ids: list[int] | None = None,
    ) -> tuple[Enrollment, bool]:
        """Grant student access when the target (or, if unspecified, the
        course's first) delivery format has a zero-price plan -- bypassing
        payment entirely but still applying that format's cohort/slot setup,
        the same as a paid checkout would (see `apply_delivery_setup`).
        Target format can be identified either by `delivery_format_id` or by
        `pricing_plan_id` (e.g. a cart item only carries the latter)."""
        if user.role != User.RoleChoices.STUDENT:
            raise EnrollmentRoleError("Only students can enroll in free courses.")
        if course.status != Course.StatusChoices.PUBLISHED or course.is_deleted:
            raise CourseNotEnrollableError("Only published courses are available for enrollment.")

        free_plans = PricingPlan.objects.filter(
            delivery_format__course=course, price=Decimal("0.00"),
        ).select_related("delivery_format")
        if pricing_plan_id is not None:
            plan = free_plans.filter(id=pricing_plan_id).first()
        elif delivery_format_id is not None:
            plan = free_plans.filter(delivery_format_id=delivery_format_id).first()
        else:
            plan = free_plans.order_by("delivery_format_id").first()
        if plan is None:
            raise FreeEnrollmentUnavailableError("This course is not available for free enrollment.")
        delivery_format = plan.delivery_format

        if delivery_format.format_type == CourseDeliveryFormat.FormatType.GROUP and cohort_id is None:
            raise FreeEnrollmentUnavailableError("Select a group to join before enrolling.")
        if delivery_format.format_type == CourseDeliveryFormat.FormatType.INDIVIDUAL and not schedule_slot_ids:
            raise FreeEnrollmentUnavailableError("Select your session times before enrolling.")

        student_profile = cls._student_profile_for_user(user)
        enrollment, created = Enrollment.all_objects.get_or_create(
            student_profile=student_profile,
            course=course,
            defaults={
                "access_status": Enrollment.AccessStatusChoices.ACTIVE,
                "access_until": None,
                "order_id": None,
                "delivery_format": delivery_format,
            },
        )

        if not created and enrollment.delivery_format_id is None:
            enrollment.delivery_format = delivery_format
            enrollment.save(update_fields=["delivery_format"])

        if not created and (enrollment.is_deleted or not enrollment.has_active_access):
            enrollment.access_status = Enrollment.AccessStatusChoices.ACTIVE
            enrollment.access_until = None
            enrollment.order_id = None
            enrollment.is_deleted = False
            enrollment.save(
                update_fields=["access_status", "access_until", "order_id", "is_deleted"]
            )

        cls.apply_delivery_setup(enrollment, cohort_id=cohort_id, schedule_slot_ids=schedule_slot_ids)

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
