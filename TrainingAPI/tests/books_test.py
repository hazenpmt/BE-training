from main import app
import json
import unittest
import uuid

from app.databases.mongodb import MongoDB


class BooksTests(unittest.TestCase):
    """ Unit testcases for REST APIs """

    def test_get_all_books(self):
        request, response = app.test_client.get(
            '/v1/books/', server_kwargs={'register_sys_signals': False}
        )
        self.assertEqual(response.status, 200)
        data = json.loads(response.text)
        self.assertGreaterEqual(data.get('n_books'), 0)
        self.assertIsInstance(data.get('books'), list)

    def test_create_and_get_book(self):
        payload = {
            'title': 'Test book ' + uuid.uuid4().hex,
            'authors': ['Test author'],
            'publisher': 'Test publisher'
        }
        database = MongoDB()
        self.addCleanup(database.client.close)
        self.addCleanup(database._books_col.delete_many, {'title': payload['title']})
        server_kwargs = {'register_sys_signals': False}

        request, response = app.test_client.post(
            '/v1/books/', json=payload, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.text).get('status'), 'success')

        request, response = app.test_client.get(
            '/v1/books/', server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)
        books = json.loads(response.text)['books']
        created_books = [book for book in books if book['title'] == payload['title']]
        self.assertEqual(len(created_books), 1)
        book_id = created_books[0]['_id']

        request, response = app.test_client.get(
            '/v1/books/' + book_id, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)
        book = json.loads(response.text)
        self.assertEqual(book['_id'], book_id)
        self.assertEqual(book['title'], payload['title'])
        self.assertEqual(book['authors'], payload['authors'])
        self.assertEqual(book['publisher'], payload['publisher'])

    def test_update_book(self):
        book_id = str(uuid.uuid4())
        database = MongoDB()
        self.addCleanup(database.client.close)
        self.addCleanup(database._books_col.delete_one, {'_id': book_id})
        database._books_col.insert_one({
            '_id': book_id,
            'title': 'Before update',
            'authors': ['Original author'],
            'publisher': 'Original publisher',
            'owner': 'original-owner'
        })
        payload = {
            'title': 'After update',
            'authors': ['Updated author'],
            'publisher': 'Updated publisher',
            '_id': 'must-not-change',
            'owner': 'must-not-change'
        }
        server_kwargs = {'register_sys_signals': False}

        request, response = app.test_client.put(
            '/v1/books/' + book_id, json=payload, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)

        request, response = app.test_client.get(
            '/v1/books/' + book_id, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)
        book = json.loads(response.text)
        self.assertEqual(book['_id'], book_id)
        self.assertEqual(book['owner'], 'original-owner')
        self.assertEqual(book['title'], payload['title'])
        self.assertEqual(book['authors'], payload['authors'])
        self.assertEqual(book['publisher'], payload['publisher'])

    def test_delete_book(self):
        book_id = str(uuid.uuid4())
        database = MongoDB()
        self.addCleanup(database.client.close)
        self.addCleanup(database._books_col.delete_one, {'_id': book_id})
        database._books_col.insert_one({
            '_id': book_id,
            'title': 'Book to delete',
            'authors': ['Test author'],
            'publisher': 'Test publisher'
        })
        server_kwargs = {'register_sys_signals': False}

        request, response = app.test_client.delete(
            '/v1/books/' + book_id, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 200)
        self.assertIsNone(database._books_col.find_one({'_id': book_id}))

        request, response = app.test_client.delete(
            '/v1/books/' + book_id, server_kwargs=server_kwargs
        )
        self.assertEqual(response.status, 404)

    def test_create_book_missing_authors(self):
        payload = {
            'title': 'Invalid test book ' + uuid.uuid4().hex,
            'publisher': 'Test publisher'
        }
        database = MongoDB()
        self.addCleanup(database.client.close)
        self.addCleanup(database._books_col.delete_many, {'title': payload['title']})

        request, response = app.test_client.post(
            '/v1/books/', json=payload,
            server_kwargs={'register_sys_signals': False}
        )
        self.assertEqual(response.status, 400)
        self.assertIsNone(database._books_col.find_one({'title': payload['title']}))

    # TODO: unittest for another apis


if __name__ == '__main__':
    unittest.main()
