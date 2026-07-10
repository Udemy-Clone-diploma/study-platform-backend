"""Notification channel preference defaults and resolution helpers.

Effective preferences for a user are the defaults below with the user's stored
overrides applied on top. In-app creation and email delivery both gate on the
resolved value. Adding a new notification type means adding one entry here.
"""

CHANNELS = ("in_app", "email")

DEFAULT_NOTIFICATION_PREFERENCES = {
    "new_message": {"in_app": True, "email": False},
    "homework_graded": {"in_app": True, "email": True},
    "schedule_event": {"in_app": True, "email": True},
    "new_lesson": {"in_app": True, "email": False},
    "course_completed": {"in_app": True, "email": True},
}


def effective_preferences(overrides: dict) -> dict:
    """Full per-type channel map for one user: defaults with overrides applied."""
    resolved = {}
    for ntype, defaults in DEFAULT_NOTIFICATION_PREFERENCES.items():
        merged = dict(defaults)
        for channel, value in overrides.get(ntype, {}).items():
            if channel in CHANNELS:
                merged[channel] = bool(value)
        resolved[ntype] = merged
    return resolved


def channel_enabled(overrides: dict, ntype: str, channel: str) -> bool:
    """Whether one channel is on for one type, honoring overrides then defaults."""
    override = overrides.get(ntype, {})
    if channel in override:
        return bool(override[channel])
    return DEFAULT_NOTIFICATION_PREFERENCES.get(ntype, {}).get(channel, False)
