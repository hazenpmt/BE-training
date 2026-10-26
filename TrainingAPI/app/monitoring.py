import asyncio
import json as json_module
import time

from pymongo import MongoClient
from sanic import Blueprint
from sanic.log import logger
from sanic.response import json, text

from config import MongoDBConfig


monitoring = Blueprint('monitoring')


async def start_monitoring(app):
    app.ctx.health_mongo = MongoClient(
        MongoDBConfig.CONNECTION_URL, serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000, socketTimeoutMS=2000
    )


async def stop_monitoring(app):
    app.ctx.health_mongo.close()
    cache = getattr(app.ctx, 'cache', None)
    if cache:
        await cache.disconnect()


async def start_request_timer(request):
    request.ctx.started_at = time.perf_counter()


async def record_request(request, response):
    if request.path in ('/metrics', '/health'):
        return
    route = request.route.name if request.route else 'unmatched'
    field = f'{request.method}|{route}|{response.status}'
    elapsed = time.perf_counter() - getattr(request.ctx, 'started_at', time.perf_counter())
    prefix = request.app.config.METRICS_PREFIX
    try:
        async with request.app.ctx.cache.client.pipeline(transaction=True) as pipe:
            pipe.hincrby(prefix + ':requests', field, 1)
            pipe.hincrbyfloat(prefix + ':seconds', field, max(0, elapsed))
            await pipe.execute()
    except Exception:
        # Observability must not turn a completed API request into an error.
        logger.warning('Unable to store request metrics')


@monitoring.get('/health')
async def health(request):
    results = await asyncio.gather(
        asyncio.to_thread(request.app.ctx.health_mongo.admin.command, 'ping'),
        request.app.ctx.cache.client.ping(), return_exceptions=True
    )
    services = {name: not isinstance(result, BaseException)
                for name, result in zip(('mongodb', 'redis'), results)}
    healthy = all(services.values())
    return json({'status': 'ok' if healthy else 'unhealthy', 'services': services},
                status=200 if healthy else 503)


@monitoring.get('/metrics')
async def metrics(request):
    prefix = request.app.config.METRICS_PREFIX
    counts, seconds = await asyncio.gather(
        request.app.ctx.cache.client.hgetall(prefix + ':requests'),
        request.app.ctx.cache.client.hgetall(prefix + ':seconds')
    )
    lines = ['# HELP training_http_requests_total Completed HTTP requests by method, route and status.',
             '# TYPE training_http_requests_total counter',
             '# HELP training_http_request_duration_seconds Request processing duration in seconds.',
             '# TYPE training_http_request_duration_seconds summary']
    for field, count in sorted(counts.items()):
        method, route, status = field.split('|')
        labels = ','.join(f'{name}={json_module.dumps(value)}' for name, value in
                          (('method', method), ('route', route), ('status', status)))
        lines.append(f'training_http_requests_total{{{labels}}} {count}')
        lines.append(f'training_http_request_duration_seconds_count{{{labels}}} {count}')
        lines.append(f'training_http_request_duration_seconds_sum{{{labels}}} {seconds.get(field, "0")}')
    return text('\n'.join(lines) + '\n', content_type='text/plain; version=0.0.4')
