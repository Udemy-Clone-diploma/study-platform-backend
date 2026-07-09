"""Celery tasks for notifications: heavy fan-out and email delivery.

Everything here runs in a worker off the request path. `fan_out_new_lesson`
does the recipient query, row creation, and email batching for a new lesson, so
the teacher's request only enqueues it (via `transaction.on_commit` in the
signal) and returns. Email sending has automatic retries on transient
mail-server / network failures. Under `CELERY_TASK_ALWAYS_EAGER` (tests) tasks
run inline, and calling a task directly still executes the body synchronously.
"""

from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail, send_mass_mail

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.enrollments.models import Enrollment
from apps.notifications.models import Notification
from apps.users.models import User

# Shared retry policy for the email-sending tasks.
_EMAIL_RETRY = {
    "autoretry_for": (SMTPException, OSError),
    "retry_backoff": True,
    "retry_kwargs": {"max_retries": 3},
}


def _render_message(body: str, link_url: str | None) -> str:
    if link_url:
        return f"{body}\n\n{settings.FRONTEND_URL}{link_url}"
    return body


@shared_task(**_EMAIL_RETRY)
def send_notification_email(
    *, email: str, title: str, body: str, link_url: str | None
) -> None:
    """Send one notification email (single-recipient `create` path)."""
    send_mail(
        subject=title,
        message=_render_message(body, link_url),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
    )


@shared_task(**_EMAIL_RETRY)
def send_notification_emails(
    *, emails: list[str], title: str, body: str, link_url: str | None
) -> None:
    """Send the same notification email to many recipients over one SMTP
    connection. One envelope per recipient so addresses are not disclosed."""
    message = _render_message(body, link_url)
    send_mass_mail(
        [(title, message, settings.DEFAULT_FROM_EMAIL, [email]) for email in emails]
    )


@shared_task
def fan_out_new_lesson(lesson_id: int) -> None:
    """Fan a `new_lesson` notification out to every student with active access.

    Runs off the request path. Re-reads the lesson (it may have been deleted, or
    its course unpublished, between enqueue and execution) before fanning out.
    """
    # Imported here to avoid a circular import: the service imports this module.
    from apps.notifications.services import NotificationService

    lesson = (
        Lesson.objects.select_related("module__course").filter(id=lesson_id).first()
    )
    if lesson is None:
        return

    course = lesson.module.course
    if course.status != Course.StatusChoices.PUBLISHED:
        return

    recipient_ids = (
        Enrollment.objects.with_active_access()
        .filter(course_id=course.id)
        .values_list("student_profile__user_id", flat=True)
    )
    recipients = list(User.objects.filter(id__in=list(recipient_ids)))

    NotificationService.fan_out(
        recipients=recipients,
        type=Notification.TypeChoices.NEW_LESSON,
        title=course.title,
        body=f"New lesson published: {lesson.title}",
        link_url=f"/learn/{course.slug}/{lesson.id}",
        payload={
            "course_slug": course.slug,
            "lesson_id": lesson.id,
            "module_id": lesson.module_id,
        },
    )
