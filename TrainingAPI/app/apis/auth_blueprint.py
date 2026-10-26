from asyncio import to_thread
import uuid
import jwt

from sanic import Blueprint
from sanic.response import json

from app.databases.mongodb import MongoDB
from app.decorators.json_validator import validate_with_jsonschema
from app.hooks.error import error_response
from app.utils.password_utils import hash_password, verify_password
from app.utils.jwt_utils import token_pair, decode_token
from app.decorators.auth import protected, admin_only


auth_bp = Blueprint('auth_blueprint', url_prefix='/auth')
_db = MongoDB()


@auth_bp.listener('before_server_start')
async def setup_sessions(app, loop):
    _db.ensure_session_index()

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

    session_id = str(uuid.uuid4())
    tokens, access, refresh = token_pair(user['username'], user.get('role', 'user'), session_id)
    await to_thread(_db.save_session, session_id, user['username'], access, refresh)
    return json(tokens)


refresh_schema = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'refresh_token': {'type': 'string', 'minLength': 1}},
    'required': ['refresh_token']
}


@auth_bp.post('/refresh')
@validate_with_jsonschema(jsonschema=refresh_schema)
async def refresh_tokens(request):
    try:
        old = decode_token(request.json['refresh_token'], 'refresh')
    except jwt.InvalidTokenError:
        return error_response(401, 'Invalid or expired refresh token')
    user = await to_thread(_db.get_user_by_username, old['username'])
    if not user:
        return error_response(401, 'Invalid or expired refresh token')
    tokens, access, refresh = token_pair(user['username'], user.get('role', 'user'), old['sid'])
    if not await to_thread(_db.rotate_session, old, access, refresh):
        return error_response(401, 'Invalid or expired refresh token')
    return json(tokens)


@auth_bp.post('/logout')
@protected
async def logout(request, username=None):
    await to_thread(_db.revoke_session, request.ctx.auth['sid'], username)
    return json({'status': 'success'})


@auth_bp.get('/users')
@admin_only
async def users(request, username=None):
    return json({'users': await to_thread(_db.list_users)})
