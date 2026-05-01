class CoursesError(Exception):
    """Base class for all domain errors raised by the courses app."""


class InvalidPricingError(CoursesError):
    """Course pricing data is inconsistent (e.g., paid course with non-positive price)."""
