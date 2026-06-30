from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.preferences import channel_enabled
from apps.notifications.tasks import send_notification_email


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
            send_notification_email.delay(
                email=recipient.email, title=title, body=body, link_url=link_url
            )

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
            send_notification_email.delay(
                email=email, title=title, body=body, link_url=link_url
            )

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
