from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from apps.payments.models import TeacherPayout

from .exceptions import PaymentError
from .liqpay import LiqPayService
from .payout_providers import (
    LiqPaySandboxPayoutProvider,
    PayoutProviderResult,
    SimulatedLiqPayPayoutProvider,
)
from .teacher_finance import TeacherFinanceService


class PayoutExecutionService:
    @staticmethod
    def _payout_mode() -> str:
        return (
            str(
                getattr(
                    settings,
                    "LIQPAY_PAYOUT_MODE",
                    "simulated",
                )
            )
            .strip()
            .lower()
        )

    @classmethod
    def _provider_for_mode(
        cls,
        mode: str,
    ):
        mode = str(mode or "").strip().lower()

        if mode == "simulated":
            (SimulatedLiqPayPayoutProvider.validate_configuration())

            return SimulatedLiqPayPayoutProvider

        if mode == "liqpay_sandbox":
            LiqPayService._ensure_liqpay_payout_sandbox()
            return LiqPaySandboxPayoutProvider

        raise PaymentError("Unsupported teacher payout mode.")

    @classmethod
    @transaction.atomic
    def _prepare_payout_execution(
        cls,
        payout: TeacherPayout,
        *,
        payout_mode: str,
    ) -> tuple[TeacherPayout, bool]:
        TeacherFinanceService._lock_teacher(payout.teacher_id)

        payout = TeacherPayout.objects.select_for_update().get(pk=payout.pk)

        if payout.provider != TeacherPayout.ProviderChoices.LIQPAY:
            raise PaymentError("Teacher payout is not a LiqPay payout.")

        payout_mode = str(payout_mode or "").strip().lower()

        if not payout_mode:
            raise PaymentError("Teacher payout execution mode is required.")

        if payout.status == TeacherPayout.StatusChoices.SUCCEEDED:
            return payout, False

        if payout.status in {
            TeacherPayout.StatusChoices.FAILED,
            TeacherPayout.StatusChoices.CANCELED,
        }:
            raise PaymentError("Finished payout cannot be executed.")

        existing_mode = (
            str(
                (payout.metadata or {}).get(
                    "payout_mode",
                    "",
                )
            )
            .strip()
            .lower()
        )

        # A PROCESSING payout may already have reached
        # the external provider. Never infer/change its
        # provider mode from the current environment.
        if payout.status == TeacherPayout.StatusChoices.PROCESSING:
            if not existing_mode:
                raise PaymentError("Processing payout has no recorded execution mode.")

            if existing_mode != payout_mode:
                raise PaymentError("Teacher payout execution mode cannot be changed.")

            return payout, False

        # From this point the payout is still PENDING.

        if existing_mode and existing_mode != payout_mode:
            raise PaymentError("Teacher payout execution mode cannot be changed.")

        update_fields = []

        if not payout.provider_order_id:
            payout.provider_order_id = f"nexo-teacher-payout-{payout.id}"

            update_fields.append("provider_order_id")

        # Persist the mode BEFORE moving to PROCESSING.
        if not existing_mode:
            payout.metadata = {
                **(payout.metadata or {}),
                "payout_mode": payout_mode,
            }

            update_fields.append("metadata")

        if update_fields:
            update_fields.append("updated_at")

            payout.save(update_fields=update_fields)

        payout = TeacherFinanceService.mark_payout_processing(
            payout,
            provider_status="request_pending",
        )

        return payout, True

    @classmethod
    @transaction.atomic
    def _store_provider_result(
        cls,
        *,
        payout: TeacherPayout,
        result: PayoutProviderResult,
    ) -> TeacherPayout:
        payout = TeacherPayout.objects.select_for_update().get(pk=payout.pk)

        payout_mode = (
            str(
                (payout.metadata or {}).get(
                    "payout_mode",
                    "",
                )
            )
            .strip()
            .lower()
        )

        payout.metadata = {
            **(payout.metadata or {}),
            "provider_response": result.raw,
            "request_uncertain": False,
        }

        if payout_mode:
            payout.metadata["payout_mode"] = payout_mode

        payout.provider_status = result.provider_status

        update_fields = [
            "metadata",
            "provider_status",
            "updated_at",
        ]

        if result.provider_payment_id:
            payout.provider_payment_id = result.provider_payment_id

            update_fields.append("provider_payment_id")

        if result.provider_transaction_id:
            payout.provider_transaction_id = result.provider_transaction_id

            update_fields.append("provider_transaction_id")

        payout.save(update_fields=update_fields)

        return payout

    @classmethod
    @transaction.atomic
    def _mark_payout_request_uncertain(
        cls,
        *,
        payout: TeacherPayout,
        error: Exception,
    ) -> TeacherPayout:
        payout = TeacherPayout.objects.select_for_update().get(pk=payout.pk)

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            return payout

        payout.provider_status = "request_uncertain"

        payout.metadata = {
            **(payout.metadata or {}),
            "request_uncertain": True,
            "request_error": str(error),
        }

        payout.save(
            update_fields=[
                "provider_status",
                "metadata",
                "updated_at",
            ]
        )

        return payout

    @classmethod
    def execute_teacher_payout(
        cls,
        *,
        payout: TeacherPayout,
        client_ip: str = "",
    ) -> TeacherPayout:

        payout_mode = cls._payout_mode()

        provider = cls._provider_for_mode(payout_mode)

        if payout_mode == "liqpay_sandbox" and not str(client_ip or "").strip():
            raise PaymentError("Client IP is required for LiqPay payout.")

        payout, should_send = cls._prepare_payout_execution(
            payout,
            payout_mode=payout_mode,
        )

        if not should_send:
            return payout
        # IMPORTANT:
        # external HTTP execution happens AFTER
        # _prepare_payout_execution transaction committed.
        try:
            result = provider.execute(
                payout=payout,
                client_ip=client_ip,
            )
        except Exception as exc:
            cls._mark_payout_request_uncertain(
                payout=payout,
                error=exc,
            )
            raise

        payout = cls._store_provider_result(
            payout=payout,
            result=result,
        )

        if result.status == LiqPaySandboxPayoutProvider.SUCCEEDED:
            return TeacherFinanceService.mark_payout_succeeded(
                payout,
                provider_status=(result.provider_status),
                provider_payment_id=(result.provider_payment_id),
                provider_transaction_id=(result.provider_transaction_id),
            )

        if result.status == LiqPaySandboxPayoutProvider.FAILED:
            reason = str(result.raw.get("err_description") or "Provider rejected payout.")

            return TeacherFinanceService.mark_payout_failed(
                payout,
                provider_status=(result.provider_status),
                reason=reason,
            )

        # Provider accepted the request but
        # no final result yet.
        payout.provider_status = result.provider_status

        payout.save(
            update_fields=[
                "provider_status",
                "updated_at",
            ]
        )

        return payout

    @classmethod
    def reconcile_teacher_payout(
        cls,
        *,
        payout: TeacherPayout,
    ) -> TeacherPayout:
        payout = TeacherPayout.objects.get(pk=payout.pk)

        if payout.status == TeacherPayout.StatusChoices.SUCCEEDED:
            return payout

        if payout.status in {
            TeacherPayout.StatusChoices.FAILED,
            TeacherPayout.StatusChoices.CANCELED,
        }:
            return payout

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            raise PaymentError("Only processing payout can be reconciled.")

        if not payout.provider_order_id:
            raise PaymentError("Teacher payout provider_order_id is required for reconciliation.")

        payout_mode = (
            str(
                (payout.metadata or {}).get(
                    "payout_mode",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if not payout_mode:
            raise PaymentError("Teacher payout execution mode was not recorded.")

        provider = cls._provider_for_mode(payout_mode)

        # No DB transaction around provider I/O.
        try:
            result = provider.reconcile(
                payout=payout,
            )
        except Exception as exc:
            cls._store_reconciliation_error(
                payout=payout,
                error=exc,
            )
            raise

        payout = cls._store_provider_result(
            payout=payout,
            result=result,
        )

        if result.status == LiqPaySandboxPayoutProvider.SUCCEEDED:
            return TeacherFinanceService.mark_payout_succeeded(
                payout,
                provider_status=(result.provider_status),
                provider_payment_id=(result.provider_payment_id),
                provider_transaction_id=(result.provider_transaction_id),
            )

        if result.status == LiqPaySandboxPayoutProvider.FAILED:
            reason = str(result.raw.get("err_description") or "Provider rejected payout.")

            return TeacherFinanceService.mark_payout_failed(
                payout,
                provider_status=(result.provider_status),
                reason=reason,
            )

        # Still not final.
        return payout

    @classmethod
    @transaction.atomic
    def _store_reconciliation_error(
        cls,
        *,
        payout: TeacherPayout,
        error: Exception,
    ) -> TeacherPayout:
        payout = TeacherPayout.objects.select_for_update().get(pk=payout.pk)

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            return payout

        payout.metadata = {
            **(payout.metadata or {}),
            "last_reconciliation_error": (str(error)),
        }

        payout.save(
            update_fields=[
                "metadata",
                "updated_at",
            ]
        )

        return payout

    @classmethod
    def handle_liqpay_payout_callback(
        cls,
        *,
        data: str,
        signature: str,
    ) -> TeacherPayout:
        data = str(data or "").strip()
        signature = str(signature or "").strip()

        if not data or not signature:
            raise PaymentError("LiqPay payout callback data and signature are required.")

        # Never trust callback payload before
        # signature validation.
        if not LiqPayService._liqpay_verify_signature(
            data=data,
            signature=signature,
        ):
            raise PaymentError("Invalid LiqPay payout callback signature.")

        payload = LiqPayService._liqpay_decode_data(data)

        provider_order_id = str(payload.get("order_id") or "").strip()

        if not provider_order_id:
            raise PaymentError("LiqPay payout callback order_id is missing.")

        provider_status = str(payload.get("status") or "").strip().lower()

        if not provider_status:
            raise PaymentError("LiqPay payout callback status is missing.")

        # Merchant correlation.
        if payload.get("public_key") != LiqPayService._liqpay_public_key():
            raise PaymentError("LiqPay payout callback public_key does not match.")

        try:
            version = int(payload.get("version"))
        except (TypeError, ValueError) as exc:
            raise PaymentError("Invalid LiqPay payout callback version.") from exc

        if version != LiqPayService._liqpay_api_version():
            raise PaymentError("LiqPay payout callback API version does not match.")

        action = str(payload.get("action") or "").strip().lower()

        if action != "p2pcredit":
            raise PaymentError("Unexpected LiqPay payout callback action.")

        payout = TeacherPayout.objects.filter(
            provider=(TeacherPayout.ProviderChoices.LIQPAY),
            provider_order_id=(provider_order_id),
        ).first()

        if payout is None:
            raise PaymentError("Teacher payout was not found.")

        payout_mode = (
            str(
                (payout.metadata or {}).get(
                    "payout_mode",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if payout_mode != "liqpay_sandbox":
            raise PaymentError("Teacher payout was not executed through LiqPay sandbox.")

        # Correlate amount when LiqPay includes it.
        if payload.get("amount") is not None:
            try:
                callback_amount = LiqPayService._decimal_money(Decimal(str(payload.get("amount"))))
            except (
                InvalidOperation,
                TypeError,
                ValueError,
            ) as exc:
                raise PaymentError("Invalid LiqPay payout callback amount.") from exc

            expected_amount = LiqPayService._decimal_money(Decimal(str(payout.amount)))

            if callback_amount != expected_amount:
                raise PaymentError("LiqPay payout callback amount does not match.")

        # Correlate currency when present.
        if payload.get("currency"):
            callback_currency = str(payload.get("currency")).strip().upper()

            if callback_currency != payout.currency.upper():
                raise PaymentError("LiqPay payout callback currency does not match.")

        result = LiqPaySandboxPayoutProvider._normalize_response(
            payout=payout,
            response=payload,
        )

        # Final states are immutable.
        if payout.status == TeacherPayout.StatusChoices.SUCCEEDED:
            if result.status == LiqPaySandboxPayoutProvider.SUCCEEDED:
                return payout

            raise PaymentError("Successful payout cannot change final status.")

        if payout.status == TeacherPayout.StatusChoices.FAILED:
            if result.status == LiqPaySandboxPayoutProvider.FAILED:
                return payout

            raise PaymentError("Failed payout cannot change final status.")

        if payout.status == TeacherPayout.StatusChoices.CANCELED:
            raise PaymentError("Canceled payout cannot process provider callback.")

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            raise PaymentError("Only processing payout can process LiqPay callback.")

        payout = cls._store_provider_result(
            payout=payout,
            result=result,
        )

        if result.status == LiqPaySandboxPayoutProvider.SUCCEEDED:
            return TeacherFinanceService.mark_payout_succeeded(
                payout,
                provider_status=(result.provider_status),
                provider_payment_id=(result.provider_payment_id),
                provider_transaction_id=(result.provider_transaction_id),
            )

        if result.status == LiqPaySandboxPayoutProvider.FAILED:
            reason = str(result.raw.get("err_description") or "Provider rejected payout.")

            return TeacherFinanceService.mark_payout_failed(
                payout,
                provider_status=(result.provider_status),
                reason=reason,
            )

        # Non-final provider status.
        return payout
