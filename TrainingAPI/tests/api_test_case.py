import os
import unittest
import uuid

from dotenv import load_dotenv

load_dotenv()
TEST_DATABASE = 'training_api_test_' + uuid.uuid4().hex
os.environ['MONGO_DATABASE'] = TEST_DATABASE

from main import app
from app.constants.cache_constants import CacheConstants
from app.databases.mongodb import MongoDB

CacheConstants.all_books = TEST_DATABASE + ':books'


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database = MongoDB()
        self.addCleanup(self.database.client.close)
        self.addCleanup(self.database.client.drop_database, TEST_DATABASE)
        self.username = 'test_' + uuid.uuid4().hex
        self.password = 'Learning123!'

    async def request(self, method, path, **kwargs):
        if kwargs.get('json') is None:
            kwargs.pop('json', None)
        try:
            _, response = await getattr(app.asgi_client, method)(path, **kwargs)
            if response.status >= 400:
                self.assertEqual(set(response.json), {'error'})
                self.assertEqual(set(response.json['error']), {'status', 'message'})
                self.assertEqual(response.json['error']['status'], response.status)
                self.assertIsInstance(response.json['error']['message'], str)
            return response
        finally:
            if hasattr(app.ctx, 'cache'):
                await app.ctx.cache.delete(CacheConstants.all_books)
                await app.ctx.cache.disconnect()

    async def register(self, username=None):
        return await self.request('post', '/v1/auth/register', json={
            'username': username or self.username, 'password': self.password
        })

    async def login(self, username=None):
        response = await self.request('post', '/v1/auth/login', json={
            'username': username or self.username, 'password': self.password
        })
        self.assertEqual(response.status, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json['token']}
