import logging
import threading

from django.conf import settings

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.preferences import channel_enabled
from apps.notifications.tasks import send_notification_email

logger = logging.getLogger(__name__)


def _dispatch_email(**kwargs) -> None:
    """Queue the email task without letting broker latency or outages block the caller's request.

    `.delay()` itself opens a connection to the broker synchronously, so a slow
    or unreachable broker can stall the request for as long as the client library
    takes to give up (observed several seconds per call on this stack, regardless
    of configured timeouts) -- unacceptable when fanning out to a whole cohort in
    one request. Doing it on a daemon thread bounds the request to the time it
    takes to start a thread, not to connect to the broker.

    Under CELERY_TASK_ALWAYS_EAGER (tests) there is no broker involved -- the task
    body just runs inline -- so dispatch synchronously there instead: tests assert
    on `mail.outbox` immediately after calling into this service, and a background
    thread would race that assertion.
    """
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        try:
            send_notification_email.delay(**kwargs)
        except Exception:
            logger.exception("Failed to queue notification email for %s", kwargs.get("email"))
        return

    def _send():
        try:
            send_notification_email.delay(**kwargs)
        except Exception:
            logger.exception("Failed to queue notification email for %s", kwargs.get("email"))

    threading.Thread(target=_send, daemon=True).start()


class NotificationService:
    """Creation, fan-out, and preference handling for notifications.

    Every domain event routes through `create` (single recipient) or `fan_out`
    (many). Both gate the in-app row and the email on the recipient's resolved
    channel preferences, so callers never touch preference logic.
    """

    @staticmethod
    def _overrides_for(user_ids: list[int]) -> dict[int, dict]:
        return {
            pref.user_id: pref.overrides
            for pref in NotificationPreference.objects.filter(user_id__in=user_ids)
        }

    @classmethod
    def create(
        cls,
        *,
        recipient,
        type: str,
        title: str,
        body: str,
        link_url: str | None = None,
        actor=None,
        payload: dict | None = None,
    ) -> Notification | None:
        overrides = cls._overrides_for([recipient.id]).get(recipient.id, {})
        if not channel_enabled(overrides, type, "in_app"):
            return None

        notification = Notification.objects.create(
            recipient=recipient,
            type=type,
            title=title,
            body=body,
            link_url=link_url,
            actor=actor,
            payload=payload or {},
        )

        if channel_enabled(overrides, type, "email"):
            _dispatch_email(email=recipient.email, title=title, body=body, link_url=link_url)

        return notification

    @classmethod
    def fan_out(
        cls,
        *,
        recipients,
        type: str,
        title: str,
        body: str,
        link_url: str | None = None,
        payload: dict | None = None,
    ) -> None:
        recipients = list(recipients)
        if not recipients:
            return

        overrides_map = cls._overrides_for([user.id for user in recipients])
        rows = []
        email_targets = []
        for user in recipients:
            overrides = overrides_map.get(user.id, {})
            if channel_enabled(overrides, type, "in_app"):
                rows.append(
                    Notification(
                        recipient=user,
                        type=type,
                        title=title,
                        body=body,
                        link_url=link_url,
                        payload=payload or {},
                    )
                )
            if channel_enabled(overrides, type, "email"):
                email_targets.append(user.email)

        if rows:
            Notification.objects.bulk_create(rows)
        for email in email_targets:
            _dispatch_email(email=email, title=title, body=body, link_url=link_url)

    @staticmethod
    def mark_all_read(user) -> int:
        return Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True
        )

    @staticmethod
    def get_overrides(user) -> dict:
        pref = NotificationPreference.objects.filter(user=user).first()
        return pref.overrides if pref else {}

    @staticmethod
    def update_preferences(user, patch: dict) -> dict:
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        overrides = pref.overrides
        for ntype, channels in patch.items():
            overrides.setdefault(ntype, {}).update(channels)
        pref.overrides = overrides
        pref.save(update_fields=["overrides", "updated_at"])
        return overrides
