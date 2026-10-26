import os

from dotenv import load_dotenv
from textwrap import dedent

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    EXPIRATION_JWT = int(os.getenv('EXPIRATION_JWT', 3600))
    REFRESH_EXPIRATION_JWT = int(os.getenv('REFRESH_EXPIRATION_JWT', 604800))

    RUN_SETTING = {
        'host': os.environ.get('SERVER_HOST', 'localhost'),
        'port': int(os.environ.get('SERVER_PORT', 8080)),
        'debug': os.getenv('DEBUG', False),
        "access_log": False,
        "auto_reload": True,
        'workers': int(os.getenv('SERVER_WORKERS', 4))
    }
    # uWSGI를 통해 배포되어야 하므로, production level에선 run setting을 건드리지 않음

    RESPONSE_TIMEOUT = 20  # seconds

    SERVER_NAME = os.getenv('SERVER_NAME')
    raw = {}
    if SERVER_NAME:
        raw['servers'] = [{'url': SERVER_NAME}]

    FALLBACK_ERROR_FORMAT = 'json'

    OAS_UI_DEFAULT = 'swagger'
    SWAGGER_UI_CONFIGURATION = {
        'apisSorter': "alpha",
        'docExpansion': "list",
        'operationsSorter': "alpha"
    }

    API_HOST = os.getenv('API_HOST', '0.0.0.0:8096')
    API_BASEPATH = os.getenv('API_BASEPATH', '')
    API_SCHEMES = os.getenv('API_SCHEMES', 'http')
    API_VERSION = os.getenv('API_VERSION', '0.0.1')
    API_TITLE = os.getenv('API_TITLE', 'Backend API')
    API_DESCRIPTION = os.getenv('API_DESCRIPTION', 'Swagger for Backend API')
    API_CONTACT_EMAIL = os.getenv('API_CONTACT_EMAIL', 'example@gmail.com')


class RedisConfig:
    HOST = os.getenv('REDIS_HOST', 'redis')
    PORT = int(os.getenv('REDIS_PORT', 6379))
    DB = int(os.getenv('REDIS_DB', 0))
    PASSWORD = os.getenv('REDIS_PASSWORD', 'pw')

    CONNECTION_URL = f"redis://{HOST}:{PORT}/{DB}"


class LocalDBConfig:
    pass


class RemoteDBConfig:
    pass


class MongoDBConfig:
    CONNECTION_URL = os.environ.get("MONGO_CONNECTION_URL")
    DATABASE = os.environ.get("MONGO_DATABASE") or "example_db"
