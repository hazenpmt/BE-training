from sanic.exceptions import SanicException
from sanic.response import json
from sanic.log import logger


def error_response(status, message):
    return json({'error': {'status': status, 'message': message}}, status=status)


async def handle_api_error(request, exception):
    status = getattr(exception, 'status_code', 500)
    if status >= 500:
        logger.error('Unhandled API error', exc_info=exception)
        message = 'Internal server error'
    else:
        message = str(exception)
    return error_response(status, message)


class _ApiError(SanicException):
    def __init__(self, message, status_code=None, quiet=None):
        super().__init__(message=message, status_code=status_code, quiet=quiet)


class ApiBadRequest(_ApiError):
    def __init__(self, message, quiet=None):
        status_code = 400
        message = 'Bad Request: ' + message
        super().__init__(message=message, status_code=status_code, quiet=quiet)


class ApiUnauthorized(_ApiError):
    def __init__(self, message, quiet=None):
        status_code = 401
        message = 'Unauthorized: ' + message
        super().__init__(message=message, status_code=status_code, quiet=quiet)


class ApiForbidden(_ApiError):
    def __init__(self, message, quiet=None):
        status_code = 403
        message = 'Forbidden: ' + message
        super().__init__(message=message, status_code=status_code, quiet=quiet)


class ApiNotFound(_ApiError):
    def __init__(self, message, quiet=None):
        status_code = 404
        message = 'Not Found: ' + message
        super().__init__(message=message, status_code=status_code, quiet=quiet)


class ApiInternalError(_ApiError):
    def __init__(self, message, quiet=None):
        status_code = 500
        message = 'Internal Error: ' + message
        super().__init__(message=message, status_code=status_code, quiet=quiet)
