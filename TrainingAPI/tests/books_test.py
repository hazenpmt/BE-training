import datetime
import uuid
from unittest.mock import patch

import jwt
from pymongo.errors import PyMongoError

from tests.api_test_case import ApiTestCase
from config import Config
from app.apis.books_blueprint import _db


class BooksTests(ApiTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.assertEqual((await self.register()).status, 201)
        self.headers = await self.login()
        self.payload = {'title': 'Test book', 'authors': ['Test author'], 'publisher': 'Test publisher'}

    async def create_book(self):
        response = await self.request('post', '/v1/books/', json=self.payload, headers=self.headers)
        self.assertEqual(response.status, 200, response.text)
        book = self.database._books_col.find_one({'owner': self.username})
        self.assertIsNotNone(book)
        return book

    async def test_create_and_public_read(self):
        book = await self.create_book()
        self.assertEqual(book['owner'], self.username)
        response = await self.request('get', '/v1/books/')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json['n_books'], 1)
        self.assertEqual(response.json['books'][0]['_id'], book['_id'])
        response = await self.request('get', '/v1/books/' + book['_id'])
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json['title'], self.payload['title'])

    async def test_owner_can_update_and_delete(self):
        book = await self.create_book()
        path = '/v1/books/' + book['_id']
        payload = dict(self.payload, title='Updated', owner='other', _id='other')
        response = await self.request('put', path, json=payload, headers=self.headers)
        self.assertEqual(response.status, 200, response.text)
        saved = self.database._books_col.find_one({'_id': book['_id']})
        self.assertEqual(saved['title'], 'Updated')
        self.assertEqual(saved['owner'], self.username)
        response = await self.request('delete', path, headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertIsNone(self.database._books_col.find_one({'_id': book['_id']}))

    async def test_other_user_cannot_update_or_delete(self):
        book = await self.create_book()
        other = 'other_' + uuid.uuid4().hex
        self.assertEqual((await self.register(other)).status, 201)
        headers = await self.login(other)
        path = '/v1/books/' + book['_id']
        response = await self.request('put', path, json=dict(self.payload, title='Forbidden'), headers=headers)
        self.assertEqual(response.status, 403)
        response = await self.request('delete', path, headers=headers)
        self.assertEqual(response.status, 403)
        self.assertEqual(self.database._books_col.find_one({'_id': book['_id']}), book)

    async def test_mutations_require_valid_token(self):
        book = await self.create_book()
        expired = jwt.encode({'username': self.username, 'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)}, Config.SECRET_KEY, algorithm='HS256')
        forged = jwt.encode({'username': self.username}, 'wrong-test-key', algorithm='HS256')
        for token in (None, 'invalid', expired, forged):
            headers = {} if token is None else {'Authorization': 'Bearer ' + token}
            for method, path, body in (('post', '/v1/books/', self.payload), ('put', '/v1/books/' + book['_id'], self.payload), ('delete', '/v1/books/' + book['_id'], None)):
                with self.subTest(method=method, token=token):
                    response = await self.request(method, path, json=body, headers=headers)
                    self.assertEqual(response.status, 401, response.text)
        self.assertEqual(self.database._books_col.count_documents({}), 1)
        self.assertEqual(self.database._books_col.find_one({'_id': book['_id']}), book)

    async def test_missing_book(self):
        path = '/v1/books/' + str(uuid.uuid4())
        for method, body in (('get', None), ('put', self.payload), ('delete', None)):
            with self.subTest(method=method):
                response = await self.request(method, path, json=body, headers=self.headers)
                self.assertEqual(response.status, 404)

    async def test_invalid_book_payload(self):
        book = await self.create_book()
        invalid = {'title': 'Missing authors', 'publisher': 'Test'}
        for method, path in (('post', '/v1/books/'), ('put', '/v1/books/' + book['_id'])):
            response = await self.request(method, path, json=invalid, headers=self.headers)
            self.assertEqual(response.status, 400)
        self.assertEqual(self.database._books_col.count_documents({}), 1)
        self.assertEqual(self.database._books_col.find_one({'_id': book['_id']}), book)

    async def test_reject_empty_or_wrong_type_fields(self):
        book = await self.create_book()
        invalid_fields = (
            {'title': ''}, {'title': '   '}, {'title': 123},
            {'publisher': ''}, {'publisher': ' \t'}, {'publisher': None},
            {'authors': []}, {'authors': ['']}, {'authors': ['   ']},
            {'authors': [123]}, {'authors': 'Tuan'}
        )
        for fields in invalid_fields:
            for method, path in (('post', '/v1/books/'), ('put', '/v1/books/' + book['_id'])):
                with self.subTest(method=method, fields=fields):
                    response = await self.request(method, path, json=dict(self.payload, **fields), headers=self.headers)
                    self.assertEqual(response.status, 400)
        self.assertEqual(self.database._books_col.count_documents({}), 1)
        self.assertEqual(self.database._books_col.find_one({'_id': book['_id']}), book)

    async def test_server_controls_new_book_id_and_owner(self):
        payload = dict(self.payload, _id='client-chosen-id', owner='someone-else')
        response = await self.request('post', '/v1/books/', json=payload, headers=self.headers)
        self.assertEqual(response.status, 200)
        book = self.database._books_col.find_one({'owner': self.username})
        self.assertIsNotNone(book)
        self.assertNotEqual(book['_id'], payload['_id'])
        self.assertEqual(str(uuid.UUID(book['_id'])), book['_id'])
        self.assertIsNone(self.database._books_col.find_one({'_id': payload['_id']}))

    async def test_malformed_json(self):
        for method, path in (('post', '/v1/books/'), ('put', '/v1/books/missing')):
            response = await self.request(
                method, path, content='{"title":',
                headers=dict(self.headers, **{'Content-Type': 'application/json'})
            )
            self.assertEqual(response.status, 400)
        self.assertEqual(self.database._books_col.count_documents({}), 0)

    async def test_database_read_failures_return_500(self):
        # Patch the driver, not the repository, to exercise exception translation.
        for operation, paths in (
            ('find', [('get', '/v1/books/', None)]),
            ('find_one', [('get', '/v1/books/missing', None),
                          ('put', '/v1/books/missing', self.payload),
                          ('delete', '/v1/books/missing', None)])
        ):
            with patch.object(_db._books_col, operation, side_effect=PyMongoError('private database details')):
                for method, path, body in paths:
                    with self.subTest(method=method, operation=operation):
                        response = await self.request(method, path, json=body, headers=self.headers)
                        self.assertEqual(response.status, 500)
                        self.assertEqual(response.json['error']['message'], 'Internal server error')

    async def test_empty_list_and_unknown_route(self):
        response = await self.request('get', '/v1/books/')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json, {'n_books': 0, 'books': []})
        response = await self.request('get', '/v1/no-such-route')
        self.assertEqual(response.status, 404)
