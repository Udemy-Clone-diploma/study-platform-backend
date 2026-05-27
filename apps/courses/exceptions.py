class CoursesError(Exception):
    """Base class for all domain errors raised by the courses app."""


class CourseNotFoundError(CoursesError):
    """No active course exists for the given slug."""


class DuplicatePricingKindError(CoursesError):
    """A PricingPlan already exists for this course and kind."""
