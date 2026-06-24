class CoursesError(Exception):
    """Base class for all domain errors raised by the courses app."""


class CourseNotFoundError(CoursesError):
    """No active course exists for the given slug."""


class DuplicatePricingKindError(CoursesError):
    """A PricingPlan already exists for this course and kind."""


class DuplicateDeliveryFormatError(CoursesError):
    """A CourseDeliveryFormat with this format_type already exists for this course."""


class PendingEditLockedError(CoursesError):
    """Operation not allowed because the pending edit is currently under moderation."""


class TeacherScheduleConflictError(CoursesError):
    """Teacher already has a class or block at the requested day and time."""


class SlotAlreadyBookedError(CoursesError):
    """The requested schedule slot is already booked by another student."""


class SlotNotAvailableError(CoursesError):
    """The requested schedule slot does not exist or belongs to a different delivery format."""


class InvalidScheduleTimeError(CoursesError):
    """end_time must be after start_time."""


class MaxStudentsReachedError(CoursesError):
    """The individual delivery format has no remaining capacity for new students."""
