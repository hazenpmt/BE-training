from asyncio import to_thread

from sanic import Blueprint
from sanic.response import json

from app.databases.mongodb import MongoDB
from app.decorators.json_validator import validate_with_jsonschema
from app.hooks.error import error_response
from app.utils.password_utils import hash_password, verify_password
from app.utils.jwt_utils import generate_jwt


auth_bp = Blueprint('auth_blueprint', url_prefix='/auth')
_db = MongoDB()

register_json_schema = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'username': {
            'type': 'string',
            'pattern': '^[A-Za-z0-9_]{3,50}$'
        },
        'password': {'type': 'string', 'minLength': 8, 'maxLength': 128}
    },
    'required': ['username', 'password']
}


@auth_bp.post('/register')
@validate_with_jsonschema(jsonschema=register_json_schema)
async def register(request):
    username = request.json['username']
    password_hash = await to_thread(hash_password, request.json['password'])
    created = await to_thread(_db.add_user, username, password_hash)

    if not created:
        return error_response(409, 'Username already exists')

    return json({'status': 'success', 'username': username}, status=201)


login_json_schema = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'username': {'type': 'string', 'minLength': 1, 'maxLength': 50},
        'password': {'type': 'string', 'minLength': 1, 'maxLength': 128}
    },
    'required': ['username', 'password']
}


@auth_bp.post('/login')
@validate_with_jsonschema(jsonschema=login_json_schema)
async def login(request):
    user = await to_thread(_db.get_user_by_username, request.json['username'])
    valid_password = False
    if user:
        valid_password = await to_thread(
            verify_password, request.json['password'], user.get('password_hash')
        )
    if not valid_password:
        return error_response(401, 'Invalid username or password')

    return json({'token': generate_jwt(user['username'])})
