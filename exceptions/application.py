class AppException(Exception):
    pass


class NotFoundException(AppException):
    pass


class ConflictException(AppException):
    pass

class ForbiddenException(Exception):
    pass

