class CurriculumError(Exception):
    """Base class for all domain errors raised by the curriculum app."""


class LessonAlreadyHasTestError(CurriculumError):
    """A TEST-type LessonItem already exists for this lesson."""


class TestNotAttemptableError(CurriculumError):
    """The test cannot be taken (e.g. it has no questions)."""


class RetakeNotAllowedError(CurriculumError):
    """The student has used all attempts allowed for this test."""
