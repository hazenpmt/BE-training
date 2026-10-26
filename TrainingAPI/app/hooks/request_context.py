from sanic.request import Request
from sanic.response import HTTPResponse, BaseHTTPResponse
from app.hooks.error import error_response


async def limit_requests(request):
    if request.method == 'OPTIONS' or not request.path.startswith('/v1/'):
        return
    config = request.app.config
    auth = request.path.rstrip('/') in ('/v1/auth/login', '/v1/auth/register', '/v1/auth/refresh')
    scope = 'auth' if auth else 'api'
    limit = config.AUTH_RATE_LIMIT_REQUESTS if auth else config.RATE_LIMIT_REQUESTS
    key = f'{config.RATE_LIMIT_PREFIX}:{scope}:{request.ip}'
    count, ttl = await request.app.ctx.cache.rate_limit(key, config.RATE_LIMIT_WINDOW)
    if count > limit:
        response = error_response(429, 'Too many requests; try again later')
        response.headers['Retry-After'] = str(max(1, ttl))
        return response


async def after_request(_: Request, response: BaseHTTPResponse) -> None:
    try:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'deny'
    finally:
        ...
