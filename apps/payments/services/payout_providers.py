from dataclasses import dataclass, field

from django.conf import settings

from apps.payments.models import TeacherPayout

from .exceptions import PaymentError
from .liqpay import LiqPayService


@dataclass(frozen=True)
class PayoutProviderResult:
    status: str
    provider_status: str
    provider_payment_id: str = ""
    provider_transaction_id: str = ""
    raw: dict = field(default_factory=dict)


class LiqPaySandboxPayoutProvider:
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PROCESSING = "processing"

    @classmethod
    def execute(
        cls,
        *,
        payout: TeacherPayout,
        client_ip: str,
    ) -> PayoutProviderResult:
        LiqPayService._ensure_liqpay_payout_sandbox()

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            raise PaymentError("Teacher payout must be processing before sending it to LiqPay.")

        if not payout.provider_order_id:
            raise PaymentError("Teacher payout provider_order_id must be saved before sending.")

        payout_request = LiqPayService._liqpay_build_payout_request(
            payout=payout,
            client_ip=client_ip,
        )

        if payout_request["provider_order_id"] != payout.provider_order_id:
            raise PaymentError("LiqPay payout order_id does not match persisted provider_order_id.")

        response = LiqPayService._liqpay_send_request(
            data=payout_request["data"],
            signature=payout_request["signature"],
            api_url=payout_request["api_url"],
        )

        return cls._normalize_response(
            payout=payout,
            response=response,
        )

    @classmethod
    def _normalize_response(
        cls,
        *,
        payout: TeacherPayout,
        response: dict,
    ) -> PayoutProviderResult:
        action = str(response.get("action") or "").lower()

        if action and action != "p2pcredit":
            raise PaymentError("Unexpected LiqPay payout action.")

        response_order_id = str(response.get("order_id") or "")

        if response_order_id and response_order_id != payout.provider_order_id:
            raise PaymentError("LiqPay payout order_id does not match.")

        response_public_key = response.get("public_key")

        if response_public_key and response_public_key != LiqPayService._liqpay_public_key():
            raise PaymentError("LiqPay payout public_key does not match.")

        response_version = response.get("version")

        if response_version is not None:
            try:
                version = int(response_version)
            except (TypeError, ValueError) as exc:
                raise PaymentError("Invalid LiqPay payout API version.") from exc

            if version != LiqPayService._liqpay_api_version():
                raise PaymentError("LiqPay payout API version does not match.")

        result = str(response.get("result") or "").lower()

        provider_status = str(response.get("status") or "").lower()

        provider_payment_id = str(response.get("payment_id") or "")

        provider_transaction_id = str(response.get("transaction_id") or "")

        safe_raw = {
            "result": response.get("result"),
            "status": response.get("status"),
            "action": response.get("action"),
            "order_id": response.get("order_id"),
            "payment_id": response.get("payment_id"),
            "transaction_id": response.get("transaction_id"),
            "liqpay_order_id": response.get("liqpay_order_id"),
            "err_code": response.get("err_code"),
            "err_description": response.get("err_description"),
        }

        if result == "ok" and provider_status in {
            "success",
            "sandbox",
        }:
            normalized_status = cls.SUCCEEDED

        elif result == "error" or provider_status in {
            "failure",
            "error",
        }:
            normalized_status = cls.FAILED

        else:
            normalized_status = cls.PROCESSING

        return PayoutProviderResult(
            status=normalized_status,
            provider_status=provider_status,
            provider_payment_id=(provider_payment_id),
            provider_transaction_id=(provider_transaction_id),
            raw=safe_raw,
        )

    @classmethod
    def reconcile(
        cls,
        *,
        payout: TeacherPayout,
    ) -> PayoutProviderResult:
        LiqPayService._ensure_liqpay_payout_sandbox()

        if not payout.provider_order_id:
            raise PaymentError("Teacher payout provider_order_id is required for reconciliation.")

        response = LiqPayService._liqpay_get_payment_status(
            provider_order_id=(payout.provider_order_id),
        )

        return cls._normalize_response(
            payout=payout,
            response=response,
        )


class SimulatedLiqPayPayoutProvider:
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PROCESSING = "processing"

    @classmethod
    def validate_configuration(cls) -> None:
        outcome = cls._outcome()

        if outcome not in {
            "success",
            "failure",
            "processing",
        }:
            raise PaymentError("Invalid simulated payout outcome.")

    @staticmethod
    def _outcome() -> str:
        return (
            str(
                getattr(
                    settings,
                    "LIQPAY_SIMULATED_PAYOUT_OUTCOME",
                    "success",
                )
            )
            .strip()
            .lower()
        )

    @classmethod
    def execute(
        cls,
        *,
        payout: TeacherPayout,
        client_ip: str = "",
    ) -> PayoutProviderResult:
        cls.validate_configuration()

        if payout.status != TeacherPayout.StatusChoices.PROCESSING:
            raise PaymentError("Teacher payout must be processing.")

        if not payout.provider_order_id:
            raise PaymentError("Teacher payout provider_order_id must be saved before execution.")

        outcome = cls._outcome()

        if outcome == "success":
            return PayoutProviderResult(
                status=cls.SUCCEEDED,
                provider_status="simulated_success",
                provider_payment_id=(f"sim-payment-{payout.id}"),
                provider_transaction_id=(f"sim-transaction-{payout.id}"),
                raw={
                    "result": "ok",
                    "status": "simulated_success",
                    "mode": "simulated",
                },
            )

        if outcome == "failure":
            return PayoutProviderResult(
                status=cls.FAILED,
                provider_status="simulated_failure",
                raw={
                    "result": "error",
                    "status": "simulated_failure",
                    "err_code": "simulated_failure",
                    "err_description": ("Simulated provider rejection."),
                    "mode": "simulated",
                },
            )

        return PayoutProviderResult(
            status=cls.PROCESSING,
            provider_status="simulated_processing",
            raw={
                "result": "ok",
                "status": "simulated_processing",
                "mode": "simulated",
            },
        )

    @classmethod
    def reconcile(
        cls,
        *,
        payout: TeacherPayout,
    ) -> PayoutProviderResult:
        return cls.execute(
            payout=payout,
        )
