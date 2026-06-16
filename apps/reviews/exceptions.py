class ReviewsError(Exception):
    """Base class for all domain errors raised by the reviews app."""


class NotEnrolledError(ReviewsError):
    """Student tried to review a course they're not enrolled in."""


class ReviewAlreadyExistsError(ReviewsError):
    """Student already submitted a review for this course."""


class ReviewEligibilityNotMetError(ReviewsError):
    """Student has not completed enough of the course to leave a review."""
