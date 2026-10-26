import datetime
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from sanic.exceptions import SanicException

from app.databases.mongodb import MongoDB
from app.hooks.error import ApiForbidden, ApiNotFound


class LibraryDB(MongoDB):
    """Data access for author references and one-copy book loans."""

    def __init__(self):
        super().__init__()
        self.authors = self.db['authors']
        self.borrows = self.db['borrows']

    def ensure_indexes(self):
        self.authors.create_index('name_key', unique=True, name='unique_author_name')
        self._books_col.create_index('author_ids', name='books_by_author')
        self.borrows.create_index(
            'book_id', unique=True, name='one_active_loan_per_book',
            partialFilterExpression={'status': 'active'}
        )
        self.borrows.create_index(
            [('username', 1), ('status', 1), ('borrowed_at', -1)],
            name='user_loan_history'
        )

    def save_author(self, name):
        name = ' '.join(name.split())
        try:
            self.authors.update_one(
                {'name_key': name.casefold()},
                {'$setOnInsert': {'_id': str(uuid.uuid4()), 'name': name,
                                  'name_key': name.casefold()}}, upsert=True
            )
        except DuplicateKeyError:
            # Another request inserted this author concurrently.
            pass
        return self.authors.find_one({'name_key': name.casefold()})

    def resolve_authors(self, names):
        authors = [self.save_author(name) for name in names]
        return list(dict.fromkeys(author['_id'] for author in authors))

    def borrow_book(self, book_id, username, days):
        book = self._books_col.find_one({'_id': book_id})
        if book is None:
            raise ApiNotFound('Book not found')
        if self._users_col.find_one({'_id': username}) is None:
            raise ApiForbidden('User no longer exists')
        now = datetime.datetime.now(datetime.timezone.utc)
        loan = {
            '_id': str(uuid.uuid4()), 'book_id': book_id, 'username': username,
            'book_title': book['title'], 'borrowed_at': now,
            'due_at': now + datetime.timedelta(days=days),
            'returned_at': None, 'status': 'active'
        }
        try:
            self.borrows.insert_one(loan)
        except DuplicateKeyError:
            raise SanicException('Book is already borrowed', status_code=409)
        return loan

    def return_book(self, loan_id, username):
        loan = self.borrows.find_one({'_id': loan_id})
        if loan is None:
            raise ApiNotFound('Borrow record not found')
        if loan['username'] != username:
            raise ApiForbidden('Only the borrower can return this book')
        result = self.borrows.find_one_and_update(
            {'_id': loan_id, 'username': username, 'status': 'active'},
            {'$set': {'status': 'returned',
                      'returned_at': datetime.datetime.now(datetime.timezone.utc)}},
            return_document=ReturnDocument.AFTER
        )
        return result or self.borrows.find_one({'_id': loan_id})


def loan_json(loan):
    result = dict(loan)
    for field in ('borrowed_at', 'due_at', 'returned_at'):
        if result.get(field):
            value = result[field]
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            result[field] = value.isoformat()
    return result
