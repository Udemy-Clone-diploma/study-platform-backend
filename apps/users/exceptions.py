class UsersError(Exception):
    """Base class for all domain errors raised by the users app."""


class AuthenticationError(UsersError):
    """Invalid credentials or account state preventing authentication."""


class EmailNotVerifiedError(UsersError):
    """The user must confirm their email before performing this action."""


class AccountForbiddenError(UsersError):
    """The account is deleted or blocked."""


class InvalidTokenError(UsersError):
    """A signed token (verification or password reset) is invalid or expired."""


class ProfileNotAvailableError(UsersError):
    """The user's role has no associated profile model."""


class SelfActionError(UsersError):
    """An administrator attempted to block or delete their own account."""


class LastAdministratorError(UsersError):
    """The action would leave the platform without an active administrator."""
