class ScheduleError(Exception):
    """Base class for all domain errors raised by the schedule app."""


class TeacherScheduleConflictError(ScheduleError):
    """Teacher already has a class or block at the requested day and time."""


class SlotAlreadyBookedError(ScheduleError):
    """The requested schedule slot is already booked by another student."""


class SlotNotAvailableError(ScheduleError):
    """The requested schedule slot does not exist or belongs to a different delivery format."""


class InvalidScheduleTimeError(ScheduleError):
    """end_time must be after start_time."""
