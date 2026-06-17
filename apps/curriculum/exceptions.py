class CurriculumError(Exception):
    """Base class for all domain errors raised by the curriculum app."""


class LessonAlreadyHasTestError(CurriculumError):
    """A TEST-type LessonItem already exists for this lesson."""
