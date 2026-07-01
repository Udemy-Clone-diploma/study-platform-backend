class EnrollmentsError(Exception):
    """Base class for all domain errors raised by the enrollments app."""


class StudentProfileRequiredError(EnrollmentsError):
    """A student profile is required to complete the enrollment."""


class CourseNotEnrollableError(EnrollmentsError):
    """The target course is not in a state that accepts new enrollments."""


class FreeEnrollmentUnavailableError(EnrollmentsError):
    """The target course does not have a free pricing plan."""


class DuplicateEnrollmentError(EnrollmentsError):
    """The student is already enrolled in the target course."""


class EnrollmentRoleError(EnrollmentsError):
    """The requesting user's role cannot create an enrollment."""


class InvalidAccessWindowError(EnrollmentsError):
    """The provided access end date is before the access grant date."""


class ActiveEnrollmentRequiredError(EnrollmentsError):
    """Caller does not hold an active enrollment for the target course."""


class LessonNotInCourseError(EnrollmentsError):
    """The requested lesson does not belong to the target course."""
