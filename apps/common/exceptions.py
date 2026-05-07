class InvalidLimitError(Exception):
    """Client supplied a non-positive or non-integer ?limit= query parameter."""
