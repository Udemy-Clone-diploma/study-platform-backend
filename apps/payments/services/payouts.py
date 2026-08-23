from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.payments.models import TeacherPayoutAccount

from .exceptions import PaymentError
from .stripe import StripeService


class PayoutService(StripeService):
    @staticmethod
    def _value(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    @classmethod
    def sync_account(cls, payout, stripe_account=None):
        if stripe_account is None:
            stripe_account = cls._load_stripe().Account.retrieve(payout.provider_account_id)
        requirements = cls._value(stripe_account, "requirements", {}) or {}
        currently_due = cls._value(requirements, "currently_due", []) or []
        disabled_reason = cls._value(requirements, "disabled_reason", "") or ""
        details = bool(cls._value(stripe_account, "details_submitted", False))
        charges = bool(cls._value(stripe_account, "charges_enabled", False))
        payouts = bool(cls._value(stripe_account, "payouts_enabled", False))
        if details and charges and payouts:
            status = TeacherPayoutAccount.StatusChoices.ACTIVE
        elif disabled_reason:
            status = TeacherPayoutAccount.StatusChoices.RESTRICTED
        elif details:
            status = TeacherPayoutAccount.StatusChoices.PENDING
        else:
            status = TeacherPayoutAccount.StatusChoices.INCOMPLETE
        payout.details_submitted = details
        payout.charges_enabled = charges
        payout.payouts_enabled = payouts
        payout.country = cls._value(stripe_account, "country", "") or ""
        payout.outstanding_requirements = list(currently_due)
        payout.disabled_reason = disabled_reason
        payout.status = status
        payout.save()
        return payout

    @classmethod
    @transaction.atomic
    def get_or_create_account(cls, teacher):
        existing = TeacherPayoutAccount.objects.select_for_update().filter(teacher=teacher).first()
        if existing:
            return existing
        stripe = cls._load_stripe()
        country = str(getattr(settings, "STRIPE_CONNECT_COUNTRY", "US")).strip().upper()
        if len(country) != 2 or not country.isalpha():
            from django.core.exceptions import ImproperlyConfigured

            raise ImproperlyConfigured(
                "STRIPE_CONNECT_COUNTRY must be a two-letter ISO country code."
            )
        account = stripe.Account.create(
            type="express",
            country=country,
            email=teacher.user.email,
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            metadata={"teacher_profile_id": str(teacher.id), "user_id": str(teacher.user_id)},
            idempotency_key=f"teacher-connect-{teacher.id}",
        )
        return TeacherPayoutAccount.objects.create(
            teacher=teacher,
            provider_account_id=account.id,
            country=cls._value(account, "country", "") or "",
        )

    @classmethod
    def create_onboarding_link(cls, teacher):
        payout = cls.get_or_create_account(teacher)
        link = cls._load_stripe().AccountLink.create(
            account=payout.provider_account_id,
            refresh_url=settings.STRIPE_CONNECT_REFRESH_URL,
            return_url=settings.STRIPE_CONNECT_RETURN_URL,
            type="account_onboarding",
        )
        return payout, link.url

    @staticmethod
    def safe_data(payout):
        if payout is None:
            return {
                "status": "not_configured",
                "configured": False,
                "details_submitted": False,
                "charges_enabled": False,
                "payouts_enabled": False,
                "outstanding_requirements": [],
                "disabled_reason": "",
            }
        return {
            "status": payout.status,
            "configured": True,
            "details_submitted": payout.details_submitted,
            "charges_enabled": payout.charges_enabled,
            "payouts_enabled": payout.payouts_enabled,
            "outstanding_requirements": payout.outstanding_requirements,
            "disabled_reason": payout.disabled_reason,
        }

    @staticmethod
    def _stripe_money(amount_minor) -> str:
        try:
            value = Decimal(str(amount_minor or 0)) / Decimal("100")
        except Exception:
            value = Decimal("0.00")

        return f"{value:.2f}"

    @classmethod
    def stripe_finance_overview(
        cls,
        payout: TeacherPayoutAccount,
        *,
        limit: int = 10,
    ) -> dict:
        if not payout or not payout.provider_account_id:
            return {
                "configured": False,
                "available": [],
                "pending": [],
                "payouts": [],
            }

        stripe = cls._load_stripe()

        safe_limit = max(
            1,
            min(int(limit or 10), 25),
        )

        try:
            balance = stripe.Balance.retrieve(
                stripe_account=payout.provider_account_id,
            )

            payout_list = stripe.Payout.list(
                limit=safe_limit,
                stripe_account=payout.provider_account_id,
            )
        except Exception as exc:
            raise PaymentError("Could not load Stripe payout information.") from exc

        def balance_rows(values):
            result = []

            for item in values or []:
                result.append(
                    {
                        "amount": cls._stripe_money(cls._value(item, "amount", 0)),
                        "currency": str(
                            cls._value(
                                item,
                                "currency",
                                "",
                            )
                            or ""
                        ).upper(),
                    }
                )

            return result

        recent_payouts = []

        for item in (
            cls._value(
                payout_list,
                "data",
                [],
            )
            or []
        ):
            recent_payouts.append(
                {
                    "id": str(cls._value(item, "id", "") or ""),
                    "amount": cls._stripe_money(cls._value(item, "amount", 0)),
                    "currency": str(
                        cls._value(
                            item,
                            "currency",
                            "",
                        )
                        or ""
                    ).upper(),
                    "status": str(
                        cls._value(
                            item,
                            "status",
                            "",
                        )
                        or ""
                    ),
                    "method": str(
                        cls._value(
                            item,
                            "method",
                            "",
                        )
                        or ""
                    ),
                    "type": str(
                        cls._value(
                            item,
                            "type",
                            "",
                        )
                        or ""
                    ),
                    "created": cls._value(
                        item,
                        "created",
                        None,
                    ),
                    "arrival_date": cls._value(
                        item,
                        "arrival_date",
                        None,
                    ),
                    "failure_code": str(
                        cls._value(
                            item,
                            "failure_code",
                            "",
                        )
                        or ""
                    ),
                    "failure_message": str(
                        cls._value(
                            item,
                            "failure_message",
                            "",
                        )
                        or ""
                    ),
                }
            )

        return {
            "configured": True,
            "available": balance_rows(
                cls._value(
                    balance,
                    "available",
                    [],
                )
            ),
            "pending": balance_rows(
                cls._value(
                    balance,
                    "pending",
                    [],
                )
            ),
            "payouts": recent_payouts,
        }
