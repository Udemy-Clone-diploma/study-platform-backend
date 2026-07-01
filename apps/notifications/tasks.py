"""Email delivery for notifications.

`send_notification_email` is a Celery task. The service calls `.delay(...)` so
SMTP work runs in a worker off the request path, with automatic retries on
transient mail-server / network failures. Under `CELERY_TASK_ALWAYS_EAGER`
(tests) it runs inline, and calling the task directly still executes the body
synchronously.
"""

from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_notification_email(
    *, email: str, title: str, body: str, link_url: str | None
) -> None:
    message = body
    if link_url:
        message = f"{body}\n\n{settings.FRONTEND_URL}{link_url}"

    send_mail(
        subject=title,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )
