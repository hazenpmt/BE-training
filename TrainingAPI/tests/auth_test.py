import time

import jwt

from tests.api_test_case import ApiTestCase
from app.utils.password_utils import verify_password
from config import Config


class AuthTests(ApiTestCase):
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
