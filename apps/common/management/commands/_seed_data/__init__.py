"""Demo content for `manage.py seed`, split out to keep the command readable.

The leading underscore keeps Django's command autodiscovery from treating this
package as a management command (`find_commands` skips packages and names
starting with `_`).

Nothing here touches the database: these modules are plain data, so the seed
command stays the single place where write order and idempotency are decided.
"""

from .courses import COURSE_CONTENT
from .finance import ORDER_SPECS, PAYOUT_SPECS
from .moderation import (
    ADMIN_NOTES,
    CHAT_SCRIPTS,
    CHAT_MODERATION,
    COURSE_MODERATION,
    HOMEWORK_SPECS,
    REVIEW_REPORTS,
    TEACHER_APPLICATIONS,
    USER_REPORTS,
)
from .people import ADMIN, MODERATORS, STUDENTS, TEACHERS

__all__ = [
    "ADMIN",
    "ADMIN_NOTES",
    "CHAT_MODERATION",
    "CHAT_SCRIPTS",
    "COURSE_CONTENT",
    "COURSE_MODERATION",
    "HOMEWORK_SPECS",
    "MODERATORS",
    "ORDER_SPECS",
    "PAYOUT_SPECS",
    "REVIEW_REPORTS",
    "STUDENTS",
    "TEACHER_APPLICATIONS",
    "TEACHERS",
    "USER_REPORTS",
]
