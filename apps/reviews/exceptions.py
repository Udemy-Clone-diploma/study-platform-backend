class ReviewsError(Exception):
    """Base class for all domain errors raised by the reviews app."""


class NotEnrolledError(ReviewsError):
    """Student tried to review a course they're not enrolled in."""


class ReviewAlreadyExistsError(ReviewsError):
    """Student already submitted a review for this course."""


class ReviewEligibilityNotMetError(ReviewsError):
    """Student has not completed enough of the course to leave a review."""


class CannotReportOwnReviewError(ReviewsError):
    """A user tried to report their own review."""


class AlreadyReportedError(ReviewsError):
    """This user has already reported this review."""


class ReviewAlreadyAssignedError(ReviewsError):
    """This flagged review already has a moderator assigned."""


class ReviewNotAssignedToModeratorError(ReviewsError):
    """The requesting moderator must assign themselves before acting on this review."""
