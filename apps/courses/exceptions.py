class CoursesError(Exception):
    """Base class for all domain errors raised by the courses app."""


class CourseNotFoundError(CoursesError):
    """No active course exists for the given slug."""


class CategoryInUseError(CoursesError):
    """The category still has courses assigned and cannot be deleted."""


class DuplicatePricingKindError(CoursesError):
    """A PricingPlan already exists for this course and kind."""


class DuplicateDeliveryFormatError(CoursesError):
    """A CourseDeliveryFormat with this format_type already exists for this course."""


class PendingEditLockedError(CoursesError):
    """Operation not allowed because the pending edit is currently under moderation."""


class MaxStudentsReachedError(CoursesError):
    """The individual delivery format has no remaining capacity for new students."""
