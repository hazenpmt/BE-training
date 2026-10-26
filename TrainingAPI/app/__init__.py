from sanic import Sanic
from sanic_cors import CORS

from app.hooks.setup_ import setup_cache
from app.misc.log import log
from config import Config


def register_extensions(sanic_app: Sanic):
    # CORs
    sanic_app.config.CORS_ORIGINS = "*"

    # OpenAPI swagger
    # sanic_app.ext.openapi.add_security_scheme('Authorization', 'apiKey', location='header', name='Authorization')
    sanic_app.ext.openapi.raw(Config.raw)

def register_routes(sanic_app: Sanic):
    from app.apis import api

    sanic_app.blueprint(api)
    from app.monitoring import monitoring
    sanic_app.blueprint(monitoring)

def register_hooks(sanic_app: Sanic):
    from app.hooks.request_context import after_request, limit_requests
    from app.hooks.error import handle_api_error
    from app.monitoring import start_request_timer, record_request, start_monitoring, stop_monitoring

    sanic_app.error_handler.add(Exception, handle_api_error)
    sanic_app.register_middleware(start_request_timer, 'request')
    sanic_app.register_middleware(limit_requests, 'request')
    sanic_app.register_middleware(after_request, 'response')
    sanic_app.register_middleware(record_request, 'response')
    sanic_app.register_listener(setup_cache, event="before_server_start")
    sanic_app.register_listener(start_monitoring, event="before_server_start")
    sanic_app.register_listener(stop_monitoring, event="after_server_stop")



def create_app(*config_cls) -> Sanic:
    log(message='Sanic application initialized with {}'.format(', '.join([config.__name__ for config in config_cls])),
        keyword='INFO')

    sanic_app = Sanic(__name__)

    for config in config_cls:
        sanic_app.config.update_config(config)

    register_extensions(sanic_app)
    register_routes(sanic_app)
    register_hooks(sanic_app)

    return sanic_app
