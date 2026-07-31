"""Suspend course access for students who missed an installment due date.

Suspension is a reversible pause, not a revoke: `Enrollment.suspend()` only
flips `access_status`, so progress/homework/materials stay untouched, and
access is restored automatically the moment any installment payment succeeds
(the generic not-active -> active branch in
`WebhookService._grant_enrollments`). Only enrollments that are currently
ACTIVE get suspended (and notified), so re-running this command while an
order stays overdue is a no-op for orders already handled -- idempotent, same
approach as prune_notifications.

    python manage.py check_overdue_installments

Run it daily from whatever scheduler you deploy with (system cron, an ECS
scheduled task, or a Kubernetes CronJob) -- there is no Celery Beat process in
this project.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.enrollments.models import Enrollment
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.payments.models import Order, PaymentInstallment


class Command(BaseCommand):
    help = "Suspend course access for orders with an overdue, unpaid installment."

    def handle(self, *args, **options):
        today = timezone.localdate()
        overdue_order_ids = (
            PaymentInstallment.objects.filter(
                due_date__lt=today,
                status__in=[
                    PaymentInstallment.StatusChoices.PENDING,
                    PaymentInstallment.StatusChoices.FAILED,
                ],
                order__payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
            )
            .exclude(
                order__status__in=[
                    Order.StatusChoices.CANCELED,
                    Order.StatusChoices.REFUNDED,
                ]
            )
            .values_list("order_id", flat=True)
            .distinct()
        )

        orders = (
            Order.objects.filter(id__in=list(overdue_order_ids))
            .select_related("student_profile__user")
            .prefetch_related("items__course")
        )

        suspended_count = 0
        for order in orders:
            course_ids = {item.course_id for item in order.items.all() if item.course_id}
            if not course_ids:
                continue

            enrollments = Enrollment.objects.filter(
                student_profile=order.student_profile,
                course_id__in=course_ids,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
            ).select_related("course")

            for enrollment in enrollments:
                enrollment.suspend()
                suspended_count += 1
                NotificationService.create(
                    recipient=order.student_profile.user,
                    type=Notification.TypeChoices.PAYMENT_OVERDUE,
                    title="Course access suspended",
                    body=(
                        f"Access to '{enrollment.course.title}' is paused: an installment "
                        "payment is overdue. Pay the outstanding amount to restore access."
                    ),
                    link_url="/student-dashboard/payment?tab=plans",
                    payload={"course_slug": enrollment.course.slug, "order_id": order.id},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Suspended {suspended_count} enrollment(s) for overdue installments."
            )
        )
