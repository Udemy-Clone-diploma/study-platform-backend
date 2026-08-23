import base64
import hashlib
import hmac
import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.payments.models import Payment, PaymentAttempt, TeacherPayout

from .base import PaymentBaseService
from .exceptions import PaymentError


class LiqPayService(PaymentBaseService):
    @staticmethod
    def _liqpay_public_key() -> str:
        public_key = getattr(settings, "LIQPAY_PUBLIC_KEY", "")
        if not public_key:
            raise ImproperlyConfigured("LIQPAY_PUBLIC_KEY is not configured.")
        return public_key

    @staticmethod
    def _liqpay_private_key() -> str:
        private_key = getattr(settings, "LIQPAY_PRIVATE_KEY", "")
        if not private_key:
            raise ImproperlyConfigured("LIQPAY_PRIVATE_KEY is not configured.")
        return private_key

    @classmethod
    def _ensure_liqpay_payout_sandbox(cls) -> None:
        public_key = str(
            cls._liqpay_public_key()
        ).strip()

        private_key = str(
            cls._liqpay_private_key()
        ).strip()

        if (
            not public_key.startswith("sandbox_")
            or not private_key.startswith("sandbox_")
        ):
            raise PaymentError(
                "Teacher payouts are allowed only "
                "with LiqPay sandbox keys."
            )

    @staticmethod
    def _liqpay_http_timeout() -> int:
        return int(
            getattr(
                settings,
                "LIQPAY_HTTP_TIMEOUT",
                10,
            )
        )

    @staticmethod
    def _liqpay_api_version() -> int:
        return int(getattr(settings, "LIQPAY_API_VERSION", 7))

    @staticmethod
    def _liqpay_api_url() -> str:
        return settings.LIQPAY_API_URL
    
    @staticmethod
    def _liqpay_checkout_url() -> str:
        return getattr(
            settings,
            "LIQPAY_CHECKOUT_URL",
            "https://www.liqpay.ua/api/3/checkout",
        )

    @classmethod
    def _liqpay_send_request(
        cls,
        *,
        data: str,
        signature: str,
        api_url: str | None = None,
    ) -> dict:
        if not data or not signature:
            raise PaymentError(
                "LiqPay request data and signature are required."
            )

        url = api_url or cls._liqpay_api_url()

        encoded_body = urlencode(
            {
                "data": data,
                "signature": signature,
            }
        ).encode("utf-8")

        request = Request(
            url,
            data=encoded_body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                request,
                timeout=cls._liqpay_http_timeout(),
            ) as response:
                raw_response = response.read()

        except HTTPError as exc:
            raise PaymentError(
                f"LiqPay API returned HTTP {exc.code}."
            ) from exc

        except URLError as exc:
            raise PaymentError(
                "Could not connect to LiqPay API."
            ) from exc

        except TimeoutError as exc:
            raise PaymentError(
                "LiqPay API request timed out."
            ) from exc

        try:
            payload = json.loads(
                raw_response.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise PaymentError(
                "Invalid response from LiqPay API."
            ) from exc

        if not isinstance(payload, dict):
            raise PaymentError(
                "Invalid response from LiqPay API."
            )

        return payload

    @classmethod
    def _liqpay_build_status_request(
        cls,
        *,
        provider_order_id: str,
    ) -> dict:
        if not provider_order_id:
            raise PaymentError(
                "LiqPay order_id is required for status request."
            )

        payload = {
            "public_key": cls._liqpay_public_key(),
            "version": cls._liqpay_api_version(),
            "action": "status",
            "order_id": provider_order_id,
        }

        data = cls._liqpay_encode_payload(payload)
        signature = cls._liqpay_sign_data(data)

        return {
            "api_url": cls._liqpay_api_url(),
            "data": data,
            "signature": signature,
        }


    @classmethod
    def _liqpay_get_payment_status(
        cls,
        *,
        provider_order_id: str,
    ) -> dict:
        status_request = cls._liqpay_build_status_request(
            provider_order_id=provider_order_id,
        )

        return cls._liqpay_send_request(
            data=status_request["data"],
            signature=status_request["signature"],
            api_url=status_request["api_url"],
        )

    @classmethod
    def _liqpay_encode_payload(cls, payload: dict) -> str:
        json_data = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return base64.b64encode(
            json_data.encode("utf-8")
        ).decode("ascii")

    @classmethod
    def _liqpay_sign_data(cls, data: str) -> str:
        private_key = cls._liqpay_private_key()

        sign_string = (
            private_key
            + data
            + private_key
        ).encode("utf-8")

        digest = hashlib.sha3_256(sign_string).digest()

        return base64.b64encode(digest).decode("ascii")

    @classmethod
    def _liqpay_verify_signature(
        cls,
        *,
        data: str,
        signature: str,
    ) -> bool:
        expected_signature = cls._liqpay_sign_data(data)

        return hmac.compare_digest(
            expected_signature,
            signature,
        )

    @staticmethod
    def _liqpay_decode_data(data: str) -> dict:
        try:
            raw = base64.b64decode(data, validate=True)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaymentError("Invalid LiqPay callback data.") from exc

        if not isinstance(payload, dict):
            raise PaymentError("Invalid LiqPay callback payload.")

        return payload

    @classmethod
    def _liqpay_build_checkout_data(
        cls,
        *,
        provider_order_id: str,
        amount: Decimal,
        currency: str,
        description: str,
        result_url: str | None = None,
        server_url: str | None = None,
    ) -> dict:
        normalized_amount = cls._decimal_money(
        Decimal(str(amount))
        )
        payload = {
            "public_key": cls._liqpay_public_key(),
            "version": cls._liqpay_api_version(),
            "action": "pay",
            "amount": f"{normalized_amount:.2f}",
            "currency": currency.upper(),
            "description": description,
            "order_id": provider_order_id,
        }

        resolved_result_url = (
            result_url
            or getattr(settings, "LIQPAY_RESULT_URL", "")
        )

        resolved_server_url = (
            server_url
            or getattr(settings, "LIQPAY_SERVER_URL", "")
        )

        if resolved_result_url:
            payload["result_url"] = resolved_result_url

        if resolved_server_url:
            payload["server_url"] = resolved_server_url

        data = cls._liqpay_encode_payload(payload)
        signature = cls._liqpay_sign_data(data)

        return {
            "checkout_url": cls._liqpay_checkout_url(),
            "data": data,
            "signature": signature,
        }

    @classmethod
    def _liqpay_build_refund_request(
        cls,
        *,
        provider_order_id: str,
        amount: Decimal,
    ) -> dict:
        if not provider_order_id:
            raise PaymentError(
                "LiqPay order_id is required for refund."
            )

        normalized_amount = cls._decimal_money(
            Decimal(str(amount))
        )

        if normalized_amount <= Decimal("0.00"):
            raise PaymentError(
                "LiqPay refund amount must be positive."
            )

        payload = {
            "public_key": cls._liqpay_public_key(),
            "version": cls._liqpay_api_version(),
            "action": "refund",
            "amount": f"{normalized_amount:.2f}",
            "order_id": provider_order_id,
        }

        data = cls._liqpay_encode_payload(payload)
        signature = cls._liqpay_sign_data(data)

        return {
            "api_url": cls._liqpay_api_url(),
            "data": data,
            "signature": signature,
        }

    @classmethod
    def _liqpay_refundable_attempt(
        cls,
        *,
        payment: Payment,
    ) -> PaymentAttempt:
        attempt = (
            payment.attempts
            .filter(
                provider=Payment.MethodChoices.LIQPAY,
                status=Payment.StatusChoices.SUCCEEDED,
            )
            .exclude(
                provider_order_id=""
            )
            .order_by(
                "-processed_at",
                "-created_at",
            )
            .first()
        )

        if attempt is None:
            raise PaymentError(
                "Successful LiqPay payment attempt was not found."
            )

        return attempt

    @classmethod
    def _liqpay_build_payout_request(
        cls,
        *,
        payout: TeacherPayout,
        client_ip: str,
        server_url: str | None = None,
    ) -> dict:
        if payout.pk is None:
            raise PaymentError(
                "Teacher payout must be saved before "
                "building a LiqPay request."
            )

        if (
            payout.provider
            != TeacherPayout.ProviderChoices.LIQPAY
        ):
            raise PaymentError(
                "Teacher payout is not a LiqPay payout."
                )

        cls._ensure_liqpay_payout_sandbox()

        amount = cls._decimal_money(
            Decimal(str(payout.amount))
        )

        if amount <= Decimal("0.00"):
            raise PaymentError(
                "Payout amount must be positive."
            )

        currency = str(
            payout.currency
        ).strip().upper()

        if currency not in {
            "UAH",
            "USD",
            "EUR",
        }:
            raise PaymentError(
                "Unsupported LiqPay payout currency."
            )

        client_ip = str(
            client_ip or ""
        ).strip()

        if not client_ip:
            raise PaymentError(
                "Client IP is required for "
                "LiqPay payout."
            )

        snapshot = (
            payout.destination_snapshot
            or {}
        )

        destination_type = str(
            snapshot.get(
                "destination_type",
                "",
            )
        ).strip()

        provider_order_id = str(
            payout.provider_order_id
            or f"nexo-teacher-payout-{payout.id}"
        ).strip()

        payload = {
            "public_key": cls._liqpay_public_key(),
            "version": cls._liqpay_api_version(),
            "action": "p2pcredit",
            "amount": f"{amount:.2f}",
            "currency": currency,
            "description": (
                f"Nexo teacher payout #{payout.id}"
            ),
            "ip": client_ip,
            "order_id": provider_order_id,
        }
        resolved_server_url = str(
            server_url
            or getattr(
                settings,
                "LIQPAY_PAYOUT_SERVER_URL",
                "",
            )
        ).strip()

        if resolved_server_url:
            payload["server_url"] = resolved_server_url

        if destination_type == "bank_account":
            required_fields = (
                "receiver_account",
                "receiver_mfo",
                "receiver_okpo",
                "receiver_company",
            )

            missing = [
                field
                for field in required_fields
                if not str(
                    snapshot.get(field, "")
                ).strip()
            ]

            if missing:
                raise PaymentError(
                    "Bank payout destination "
                    "snapshot is incomplete."
                )

            payload.update(
                {
                    "receiver_account": str(
                        snapshot[
                            "receiver_account"
                        ]
                    ).strip(),
                    "receiver_mfo": str(
                        snapshot[
                            "receiver_mfo"
                        ]
                    ).strip(),
                    "receiver_okpo": str(
                        snapshot[
                            "receiver_okpo"
                        ]
                    ).strip(),
                    "receiver_company": str(
                        snapshot[
                            "receiver_company"
                        ]
                    ).strip(),
                }
            )

        elif destination_type == "card_token":
            receiver_card_token = str(
                snapshot.get(
                    "receiver_card_token",
                    "",
                )
            ).strip()

            if not receiver_card_token:
                raise PaymentError(
                    "LiqPay card token is missing "
                    "from payout snapshot."
                )

            payload[
                "receiver_card_token"
            ] = receiver_card_token

        else:
            raise PaymentError(
                "Unsupported payout destination "
                "snapshot type."
            )

        data = cls._liqpay_encode_payload(
            payload
        )

        signature = cls._liqpay_sign_data(
            data
        )

        return {
            "api_url": cls._liqpay_api_url(),
            "data": data,
            "signature": signature,
            "provider_order_id": (
                provider_order_id
            ),
        }

    @classmethod
    def _liqpay_create_refund(
        cls,
        *,
        provider_order_id: str,
        amount: Decimal,
    ) -> dict:
        refund_request = cls._liqpay_build_refund_request(
            provider_order_id=provider_order_id,
            amount=amount,
        )

        return cls._liqpay_send_request(
            data=refund_request["data"],
            signature=refund_request["signature"],
            api_url=refund_request["api_url"],
        )