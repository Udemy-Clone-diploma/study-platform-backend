import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import PermissionDenied

from apps.users.models import StudentProfile, User

from .exceptions import PaymentError


class PaymentBaseService:
    @staticmethod
    def _student_profile_for_user(user: User) -> StudentProfile:
        if user.role != User.RoleChoices.STUDENT:
            raise PermissionDenied("Only students can create checkout sessions.")
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist as exc:
            raise PaymentError("Student profile is required for checkout.") from exc

    @staticmethod
    def _default_success_url() -> str:
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        return (
            f"{frontend_url}/student-dashboard/payment"
            "?tab=history&session_id={CHECKOUT_SESSION_ID}"
        )

    @staticmethod
    def _default_cancel_url() -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/student-dashboard/payment?tab=cart"

    @staticmethod
    def _to_minor_units(amount: Decimal) -> int:
        return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _decimal_money(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
