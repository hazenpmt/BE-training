import time
import asyncio

import jwt

from tests.api_test_case import ApiTestCase
from app.utils.password_utils import verify_password
from config import Config


class AuthTests(ApiTestCase):
    async def start_session(self):
        self.assertEqual((await self.register()).status, 201)
        response = await self.request('post', '/v1/auth/login', json={
            'username': self.username, 'password': self.password
        })
        self.assertEqual(response.status, 200)
        return response.json

    async def test_refresh_rotation(self):
        tokens = await self.start_session()
        response = await self.request('post', '/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
        self.assertEqual(response.status, 200, response.text)
        new = response.json
        self.assertNotEqual(new['token'], tokens['token'])
        self.assertNotEqual(new['refresh_token'], tokens['refresh_token'])
        response = await self.request('post', '/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
        self.assertEqual(response.status, 401)
        response = await self.request('get', '/v1/borrows', headers={'Authorization': 'Bearer ' + tokens['token']})
        self.assertEqual(response.status, 401)
        response = await self.request('get', '/v1/borrows', headers={'Authorization': 'Bearer ' + new['token']})
        self.assertEqual(response.status, 200)

    async def test_logout_revokes_both_tokens(self):
        tokens = await self.start_session()
        headers = {'Authorization': 'Bearer ' + tokens['token']}
        response = await self.request('post', '/v1/auth/logout', headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual((await self.request('get', '/v1/borrows', headers=headers)).status, 401)
        response = await self.request('post', '/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
        self.assertEqual(response.status, 401)

    async def test_token_types_cannot_be_swapped(self):
        tokens = await self.start_session()
        response = await self.request('get', '/v1/borrows', headers={'Authorization': 'Bearer ' + tokens['refresh_token']})
        self.assertEqual(response.status, 401)
        response = await self.request('post', '/v1/auth/refresh', json={'refresh_token': tokens['token']})
        self.assertEqual(response.status, 401)
        for body, status in (({}, 400), ({'refresh_token': 'invalid'}, 401)):
            self.assertEqual((await self.request('post', '/v1/auth/refresh', json=body)).status, status)

    async def test_admin_endpoint_and_role_changes(self):
        tokens = await self.start_session()
        headers = {'Authorization': 'Bearer ' + tokens['token']}
        self.assertEqual((await self.request('get', '/v1/auth/users')).status, 401)
        self.assertEqual((await self.request('get', '/v1/auth/users', headers=headers)).status, 403)
        # Test fixture assigns the role; the public registration API cannot.
        self.database._users_col.update_one({'_id': self.username}, {'$set': {'role': 'admin'}})
        response = await self.request('get', '/v1/auth/users', headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json['users'], [{'username': self.username, 'role': 'admin'}])
        self.database._users_col.update_one({'_id': self.username}, {'$set': {'role': 'user'}})
        self.assertEqual((await self.request('get', '/v1/auth/users', headers=headers)).status, 403)

    async def test_logout_does_not_revoke_other_sessions(self):
        tokens = await self.start_session()
        other_headers = await self.login()
        await self.request('post', '/v1/auth/logout', headers={'Authorization': 'Bearer ' + tokens['token']})
        self.assertEqual((await self.request('get', '/v1/borrows', headers=other_headers)).status, 200)

    async def test_refresh_rotation_is_atomic(self):
        tokens = await self.start_session()
        from app.apis.auth_blueprint import _db
        from app.utils.jwt_utils import decode_token, token_pair

        old = decode_token(tokens['refresh_token'], 'refresh')
        _, access1, refresh1 = token_pair(self.username, 'user', old['sid'])
        _, access2, refresh2 = token_pair(self.username, 'user', old['sid'])
        results = await asyncio.gather(
            asyncio.to_thread(_db.rotate_session, old, access1, refresh1),
            asyncio.to_thread(_db.rotate_session, old, access2, refresh2)
        )
        self.assertEqual(sorted(results), [False, True])

    async def test_register_and_duplicate(self):
        response = await self.register()
        self.assertEqual(response.status, 201, response.text)
        self.assertEqual(response.json['username'], self.username)
        self.assertNotIn('password_hash', response.json)
        user = self.database._users_col.find_one({'_id': self.username})
        self.assertNotEqual(user['password_hash'], self.password)
        self.assertTrue(verify_password(self.password, user['password_hash']))
        self.assertEqual((await self.register()).status, 409)
        self.assertEqual(self.database._users_col.count_documents({}), 1)

    async def test_login_returns_valid_jwt(self):
        self.assertEqual((await self.register()).status, 201)
        before = int(time.time())
        headers = await self.login()
        claims = jwt.decode(headers['Authorization'].split(' ', 1)[1], Config.SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(claims['username'], self.username)
        self.assertEqual(claims['role'], 'user')
        self.assertGreaterEqual(claims['exp'], before + Config.EXPIRATION_JWT)
        self.assertNotIn('password', claims)
        self.assertNotIn('password_hash', claims)

    async def test_invalid_credentials(self):
        self.assertEqual((await self.register()).status, 201)
        errors = []
        for username, password in ((self.username, 'wrong'), ('missing', self.password)):
            response = await self.request('post', '/v1/auth/login', json={'username': username, 'password': password})
            self.assertEqual(response.status, 401)
            self.assertNotIn('token', response.json)
            errors.append(response.json)
        self.assertEqual(errors[0], errors[1])

    async def test_invalid_registration(self):
        for payload in ({}, {'username': 'ab', 'password': self.password}, {'username': self.username, 'password': 'short'}, {'username': self.username, 'password': self.password, 'role': 'admin'}):
            with self.subTest(payload=payload):
                response = await self.request('post', '/v1/auth/register', json=payload)
                self.assertEqual(response.status, 400)
        self.assertEqual(self.database._users_col.count_documents({}), 0)

    async def test_invalid_login_payload(self):
        for payload in ({}, {'username': self.username}, {'username': {'$ne': None}, 'password': self.password}):
            response = await self.request('post', '/v1/auth/login', json=payload)
            self.assertEqual(response.status, 400)
