class ReviewsError(Exception):
    """Base class for all domain errors raised by the reviews app."""


class NotEnrolledError(ReviewsError):
    """Student tried to review a course they're not enrolled in."""


class ReviewAlreadyExistsError(ReviewsError):
    """Student already submitted a review for this course."""
