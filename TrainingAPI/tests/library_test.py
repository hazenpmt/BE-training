import asyncio

from tests.api_test_case import ApiTestCase


class LibraryTests(ApiTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.assertEqual((await self.register()).status, 201)
        self.headers = await self.login()
        self.payload = {'title': 'Module 2 book', 'authors': ['Author One'], 'publisher': 'Test'}
        response = await self.request('post', '/v1/books/', json=self.payload, headers=self.headers)
        self.assertEqual(response.status, 200, response.text)
        self.book = self.database._books_col.find_one({'owner': self.username})

    async def borrow(self, headers=None, **fields):
        return await self.request('post', '/v1/borrows', headers=headers or self.headers,
                                  json=dict(book_id=self.book['_id'], **fields))

    async def test_author_references_and_filter(self):
        author = self.database.db.authors.find_one({'name': 'Author One'})
        self.assertEqual(self.book['author_ids'], [author['_id']])
        response = await self.request('post', '/v1/authors', headers=self.headers, json={'name': '  AUTHOR   ONE  '})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json['author']['_id'], author['_id'])
        self.assertEqual(self.database.db.authors.count_documents({}), 1)
        response = await self.request('get', '/v1/books/', params={'author_id': author['_id']})
        self.assertEqual(response.json['n_books'], 1)
        response = await self.request('get', '/v1/authors')
        self.assertEqual(len(response.json['authors']), 1)

    async def test_update_replaces_author_links(self):
        path = '/v1/books/' + self.book['_id']
        response = await self.request('put', path, headers=self.headers,
                                      json=dict(self.payload, authors=['Author Two'], author_ids=['forged']))
        self.assertEqual(response.status, 200)
        author = self.database.db.authors.find_one({'name': 'Author Two'})
        saved = self.database._books_col.find_one({'_id': self.book['_id']})
        self.assertEqual(saved['author_ids'], [author['_id']])

    async def test_borrow_return_and_reborrow(self):
        response = await self.borrow(days=7)
        self.assertEqual(response.status, 201, response.text)
        loan = response.json['borrow']
        self.assertEqual(loan['username'], self.username)
        self.assertEqual(loan['book_id'], self.book['_id'])
        self.assertEqual(loan['status'], 'active')
        self.assertEqual((await self.borrow()).status, 409)
        response = await self.request('get', '/v1/borrows', headers=self.headers, params={'status': 'active'})
        self.assertEqual(len(response.json['borrows']), 1)
        path = '/v1/borrows/' + loan['_id'] + '/return'
        response = await self.request('post', path, headers=self.headers)
        self.assertEqual(response.json['borrow']['status'], 'returned')
        self.assertIsNotNone(response.json['borrow']['returned_at'])
        self.assertEqual((await self.request('post', path, headers=self.headers)).status, 200)
        self.assertEqual((await self.borrow()).status, 201)
        self.assertEqual(self.database.db.borrows.count_documents({}), 2)

    async def test_other_user_cannot_return_or_read_my_history(self):
        loan = (await self.borrow()).json['borrow']
        other = self.username + '_b'
        self.assertEqual((await self.register(other)).status, 201)
        headers = await self.login(other)
        response = await self.request('post', '/v1/borrows/' + loan['_id'] + '/return', headers=headers)
        self.assertEqual(response.status, 403)
        response = await self.request('get', '/v1/borrows', headers=headers)
        self.assertEqual(response.json['borrows'], [])

    async def test_invalid_loan_requests(self):
        for days in (0, 31, '7'):
            self.assertEqual((await self.borrow(days=days)).status, 400)
        for path in ('/v1/authors', '/v1/borrows'):
            response = await self.request('post', path, json={})
            self.assertEqual(response.status, 401)
        response = await self.request('post', '/v1/borrows', headers=self.headers, json={'book_id': 'missing'})
        self.assertEqual(response.status, 404)
        response = await self.request('get', '/v1/borrows', headers=self.headers, params={'status': 'bad'})
        self.assertEqual(response.status, 400)

    async def test_unique_index_prevents_simultaneous_loans(self):
        # Exercise the repository in parallel; the database index arbitrates writes.
        from app.apis.library_blueprint import database
        from sanic.exceptions import SanicException

        async def attempt():
            try:
                await asyncio.to_thread(database.borrow_book, self.book['_id'], self.username, 14)
                return 201
            except SanicException as error:
                return error.status_code

        results = await asyncio.gather(attempt(), attempt())
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(self.database.db.borrows.count_documents({'status': 'active'}), 1)
