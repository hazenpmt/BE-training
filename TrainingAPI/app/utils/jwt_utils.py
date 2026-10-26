import datetime
import uuid

import jwt

from config import Config


def generate_jwt(username, role='user', *, token_type='access', session_id=None, token_id=None):
    lifetime = Config.EXPIRATION_JWT if token_type == 'access' else Config.REFRESH_EXPIRATION_JWT
    expiration_time = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=lifetime)
    token = jwt.encode(
        {
            "username": username,
            "role": role,
            "typ": token_type,
            "sid": session_id,
            "jti": token_id or str(uuid.uuid4()),
            "exp": expiration_time
        }, 
        Config.SECRET_KEY, algorithm='HS256'
    )

    return token


def decode_token(token, token_type):
    claims = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'], options={
        'require': ['exp', 'username', 'typ', 'sid', 'jti']
    })
    if claims['typ'] != token_type or any(
        not isinstance(claims[field], str) or not claims[field]
        for field in ('username', 'sid', 'jti')
    ):
        raise jwt.InvalidTokenError('Invalid token claims')
    return claims


def token_pair(username, role, session_id):
    access_id, refresh_id = str(uuid.uuid4()), str(uuid.uuid4())
    access = generate_jwt(username, role, session_id=session_id, token_id=access_id)
    refresh = generate_jwt(username, role, token_type='refresh', session_id=session_id, token_id=refresh_id)
    return {'token': access, 'refresh_token': refresh}, decode_token(access, 'access'), decode_token(refresh, 'refresh')
