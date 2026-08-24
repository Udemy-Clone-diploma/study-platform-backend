from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.payments.models import Order, Payment, PaymentItem

from .base import PaymentBaseService
from .exceptions import PaymentError


class InvoiceService(PaymentBaseService):
    @staticmethod
    def _money(amount: Decimal, currency: str) -> str:
        return f"{currency.upper()} {amount:,.2f}"

    @staticmethod
    def _styles() -> dict[str, ParagraphStyle]:
        styles = getSampleStyleSheet()
        body = ParagraphStyle(
            "BillingBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#3D3D3D"),
        )
        return {
            "title": ParagraphStyle(
                "BillingTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=22,
                leading=26,
                textColor=colors.HexColor("#121212"),
                spaceAfter=8,
            ),
            "body": body,
            "label": ParagraphStyle(
                "BillingLabel",
                parent=body,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#121212"),
            ),
            "footer": ParagraphStyle(
                "BillingFooter",
                parent=body,
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#6A6A6A"),
                alignment=1,
            ),
        }

    @staticmethod
    def _company_details() -> list[str]:
        details = [settings.INVOICE_COMPANY_NAME]
        if settings.INVOICE_COMPANY_EMAIL:
            details.append(settings.INVOICE_COMPANY_EMAIL)
        if settings.INVOICE_COMPANY_ADDRESS:
            details.append(settings.INVOICE_COMPANY_ADDRESS)
        return details

    @staticmethod
    def _detail(label: str, value: str) -> str:
        return f"<b>{escape(label)}</b><br/>{escape(value)}"

    @classmethod
    def _build_billing_pdf(
        cls,
        *,
        document_title: str,
        heading: str,
        detail_rows: list[tuple[tuple[str, str], tuple[str, str]]],
        item_rows: list[tuple[str, str, Decimal, str]],
        total_rows: list[tuple[str, Decimal, str]],
        footer_lines: list[str],
    ) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            title=document_title,
            author=settings.INVOICE_COMPANY_NAME,
        )
        styles = cls._styles()
        story = [
            Paragraph(heading, styles["title"]),
            Paragraph(
                "<br/>".join(escape(value) for value in cls._company_details()), styles["body"]
            ),
            Spacer(1, 12),
        ]

        details = Table(
            [
                [
                    Paragraph(cls._detail(*left), styles["body"]),
                    Paragraph(cls._detail(*right), styles["body"]),
                ]
                for left, right in detail_rows
            ],
            colWidths=[85 * mm, 85 * mm],
        )
        details.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.extend([details, Spacer(1, 12)])

        rows = [
            [
                Paragraph("Course", styles["label"]),
                Paragraph("Plan", styles["label"]),
                Paragraph("Qty", styles["label"]),
                Paragraph("Amount", styles["label"]),
            ]
        ]
        for course_title, plan_kind, amount, currency in item_rows:
            rows.append(
                [
                    Paragraph(escape(course_title), styles["body"]),
                    Paragraph(escape(plan_kind or "Course"), styles["body"]),
                    Paragraph("1", styles["body"]),
                    Paragraph(cls._money(amount, currency), styles["body"]),
                ]
            )

        items_table = Table(rows, colWidths=[75 * mm, 45 * mm, 20 * mm, 30 * mm])
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D6E0FF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#121212")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D4D4D4")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (-2, 0), (-1, -1), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        totals = Table(
            [
                [
                    Paragraph(label, styles["label"]),
                    Paragraph(
                        cls._money(amount, currency),
                        styles["label"] if index == len(total_rows) - 1 else styles["body"],
                    ),
                ]
                for index, (label, amount, currency) in enumerate(total_rows)
            ],
            colWidths=[135 * mm, 35 * mm],
        )
        totals.setStyle(
            TableStyle(
                [
                    ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#003AFF")),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend(
            [
                items_table,
                Spacer(1, 10),
                totals,
                Spacer(1, 24),
                Paragraph("<br/>".join(escape(line) for line in footer_lines), styles["footer"]),
            ]
        )
        document.build(story)
        return buffer.getvalue()

    @classmethod
    def generate_order_invoice_pdf(cls, order: Order) -> bytes:
        """Build an invoice from immutable order-item snapshots held by the backend."""
        issue_at = order.completed_at or order.created_at
        issue_date = timezone.localtime(issue_at).strftime("%d %b %Y")
        student_name = order.user.get_full_name().strip() or order.user.email
        items = list(order.items.all())
        subtotal = sum((item.unit_amount for item in items), Decimal("0.00"))
        return cls._build_billing_pdf(
            document_title=f"Invoice {order.id}",
            heading="INVOICE",
            detail_rows=[
                (("Invoice number", f"#{order.id}"), ("Issue date", issue_date)),
                (("Student", student_name), ("Payment status", order.get_status_display())),
            ],
            item_rows=[
                (item.course_title, item.pricing_plan_kind, item.unit_amount, item.currency)
                for item in items
            ],
            total_rows=[
                ("Subtotal", subtotal, order.currency),
                ("Total", order.total_amount, order.currency),
            ],
            footer_lines=["This invoice was generated automatically."],
        )

    @classmethod
    def generate_payment_receipt_pdf(cls, payment: Payment) -> bytes:
        """Build a receipt only for a payment the backend has marked successful.
        Refunded payments keep theirs: the receipt records a charge that did
        happen, and the refund does not erase it."""
        if payment.status not in {
            Payment.StatusChoices.SUCCEEDED,
            Payment.StatusChoices.REFUNDED,
        }:
            raise PaymentError("Receipt is available only after successful payment.")

        paid_at = payment.processed_at or payment.created_at
        paid_date = timezone.localtime(paid_at).strftime("%d %b %Y")
        receipt_number = f"REC-{paid_at.year}-{payment.id:06d}"
        student_name = payment.user.get_full_name().strip() or payment.user.email
        successful_attempt = (
            payment.attempts.filter(
                status=Payment.StatusChoices.SUCCEEDED,
            )
            .exclude(stripe_charge_id="")
            .first()
        )
        transaction_reference = (
            payment.stripe_payment_intent_id
            or (successful_attempt.stripe_charge_id if successful_attempt else "")
            or payment.stripe_session_id
            or f"Payment #{payment.id}"
        )
        provider = payment.get_payment_method_display()
        method = (
            "Card"
            if payment.payment_method == Payment.MethodChoices.STRIPE
            else "Manual confirmation"
        )
        payment_items = list(payment.items.all())
        item_amounts = cls._receipt_item_amounts(payment, payment_items)
        subtotal = sum(item_amounts, Decimal("0.00"))

        return cls._build_billing_pdf(
            document_title=f"Receipt {receipt_number}",
            heading="PAYMENT RECEIPT",
            detail_rows=[
                (("Receipt number", receipt_number), ("Issue date", paid_date)),
                (("Paid date", paid_date), ("Payment status", "Paid")),
                (("Student", student_name), ("Order number", f"#{payment.order_id or '—'}")),
                (("Payment provider", provider), ("Payment method", method)),
                (
                    ("Payment reference", transaction_reference),
                    ("Currency", payment.currency.upper()),
                ),
            ],
            item_rows=[
                (item.course_title, item.pricing_plan_kind, amount, item.currency)
                for item, amount in zip(payment_items, item_amounts, strict=True)
            ],
            total_rows=[
                ("Subtotal", subtotal, payment.currency),
                ("Total paid", payment.amount, payment.currency),
            ],
            footer_lines=[
                "Thank you for your payment.",
                "This receipt was generated automatically.",
                "This document confirms that payment for the listed courses has been received.",
            ],
        )

    @classmethod
    def _receipt_item_amounts(
        cls,
        payment: Payment,
        items: list[PaymentItem],
    ) -> list[Decimal]:
        if not items:
            return []
        if payment.installment_id is None or payment.order_id is None:
            return [item.unit_amount for item in items]

        installment_count = payment.order.installments_count
        remaining = payment.amount
        amounts: list[Decimal] = []
        for index, item in enumerate(items):
            if index == len(items) - 1:
                amount = remaining
            else:
                amount = cls._decimal_money(item.unit_amount / installment_count)
                remaining -= amount
            amounts.append(amount)
        return amounts
