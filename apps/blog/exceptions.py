class BlogError(Exception):
    """Base class for all domain errors raised by the blog app."""


class ArticleAlreadyAssignedError(BlogError):
    """This article already has a moderator assigned."""


class ArticleNotAssignedToModeratorError(BlogError):
    """The requesting moderator must assign themselves before acting on this article."""


class BlogCategoryInUseError(BlogError):
    """This category is still assigned to one or more articles."""
