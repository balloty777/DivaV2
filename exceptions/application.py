class AppException(Exception):
    """Base class for application-level exceptions."""


class NotFoundException(AppException):
    """Raised when a requested resource does not exist or is not accessible."""


class ConflictException(AppException):
    """Raised when a request conflicts with the current resource state."""


class ForbiddenException(AppException):
    """Raised when an authenticated user is not permitted to perform an action."""