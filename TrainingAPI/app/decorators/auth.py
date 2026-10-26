from functools import wraps
import jwt

from app.hooks.error import ApiUnauthorized, ApiForbidden
from app.utils.jwt_utils import decode_token
from app.databases.mongodb import MongoDB

_db = MongoDB()


def check_token(request):
    token = request.token
    if not token:
        return False, None

    try:
        jwt_ = decode_token(token, 'access')
        session = _db.get_session(jwt_['sid'])
        user = _db.get_user_by_username(jwt_['username'])
        if not session or session['username'] != jwt_['username'] or session['access_jti'] != jwt_['jti'] or not user:
            return False, None
        jwt_['role'] = user.get('role', 'user')
        return True, jwt_
    except jwt.exceptions.InvalidTokenError:
        return False, None


def protected(wrapped):
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            is_authenticated, jwt_ = check_token(request)

            if is_authenticated:
                request.ctx.auth = jwt_
                kwargs['username'] = jwt_['username']
                response = await f(request, *args, **kwargs)
                return response
            else:
                raise ApiUnauthorized("You are unauthorized.")

        return decorated_function

    return decorator(wrapped)


def admin_only(handler):
    @protected
    @wraps(handler)
    async def wrapped(request, username=None, **kwargs):
        if request.ctx.auth['role'] != 'admin':
            raise ApiForbidden('Admin permission required')
        return await handler(request, username=username, **kwargs)
    return wrapped
